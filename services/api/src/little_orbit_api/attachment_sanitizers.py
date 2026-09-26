"""Signature detection and metadata-removing attachment transcoders."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TypedDict, cast

import fitz  # type: ignore[import-untyped]
from PIL import Image, ImageSequence

from .attachment_media_errors import AttachmentRejected

Image.MAX_IMAGE_PIXELS = 80_000_000
MAX_MEDIA_SECONDS = 600.0
MAX_PDF_PAGES = 100
MAX_PDF_PIXELS = 300_000_000


class ProbeStream(TypedDict, total=False):
    """The ffprobe stream fields used by the media policy."""

    codec_type: str


class ProbeFormat(TypedDict, total=False):
    """The ffprobe format fields used by the media policy."""

    duration: str


class ProbeResult(TypedDict, total=False):
    """A validated ffprobe response shape."""

    streams: list[ProbeStream]
    format: ProbeFormat


def sanitize_file(source: Path, target: Path, declared_type: str) -> None:
    """Verify the byte signature and write a metadata-free accepted representation."""

    media_type = detect_media_type(source, declared_type)
    if media_type != declared_type:
        raise AttachmentRejected("media_type_mismatch")
    target.parent.mkdir(parents=True, exist_ok=True)
    if media_type.startswith("image/"):
        _sanitize_image(source, target, media_type)
    elif media_type == "application/pdf":
        _sanitize_pdf(source, target)
    elif media_type.startswith(("audio/", "video/")):
        _sanitize_media(source, target, media_type)
    else:
        _sanitize_text(source, target)


def detect_media_type(source: Path, declared_type: str) -> str:
    """Detect one allow-listed type from magic bytes, then validate its stream shape."""

    with source.open("rb") as stream:
        header = stream.read(32)
    basic = _image_or_document_type(header)
    if basic is not None:
        return basic
    media = _audio_or_container_type(source, header, declared_type)
    if media is not None:
        return media
    if declared_type in {"text/plain", "text/markdown"}:
        _read_valid_text(source)
        return declared_type
    raise AttachmentRejected("unrecognized_media_signature")


def _image_or_document_type(header: bytes) -> str | None:
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    if header.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def _audio_or_container_type(
    source: Path, header: bytes, declared_type: str
) -> str | None:
    if header.startswith(b"OggS"):
        return "audio/ogg"
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return _container_media_type(source, declared_type, {"audio/mp4", "video/mp4"})
    if header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0):
        return "audio/mpeg"
    return None


def _container_media_type(source: Path, declared: str, accepted: set[str]) -> str:
    if declared not in accepted:
        raise AttachmentRejected("media_type_mismatch")
    probe = _probe(source)
    kinds = {item.get("codec_type") for item in probe.get("streams", [])}
    if "video" in kinds:
        return "video/mp4"
    if kinds == {"audio"}:
        return "audio/mp4"
    raise AttachmentRejected("invalid_media_streams")


def _sanitize_image(source: Path, target: Path, media_type: str) -> None:
    image_format = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
        "image/gif": "GIF",
    }[media_type]
    with Image.open(source) as image:
        frames: list[Image.Image] = []
        durations: list[int] = []
        pixel_count = 0
        for source_frame in ImageSequence.Iterator(image):
            if len(frames) >= 300:
                raise AttachmentRejected("too_many_image_frames")
            pixel_count += source_frame.width * source_frame.height
            if pixel_count > 80_000_000:
                raise AttachmentRejected("image_pixel_budget_exceeded")
            durations.append(int(source_frame.info.get("duration", image.info.get("duration", 100))))
            frames.append(_clean_frame(source_frame, image_format))
        if not frames:
            raise AttachmentRejected("invalid_image")
        if len(frames) > 1 and image_format in {"GIF", "WEBP"}:
            frames[0].save(
                target,
                format=image_format,
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=image.info.get("loop", 0),
                disposal=2,
            )
        elif image_format == "JPEG":
            frames[0].save(target, format=image_format, quality=90, optimize=True)
        else:
            frames[0].save(target, format=image_format)


def _clean_frame(frame: Image.Image, image_format: str) -> Image.Image:
    if image_format == "GIF":
        clean = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        clean.alpha_composite(frame.convert("RGBA"))
        return clean
    mode = "RGB" if image_format == "JPEG" else "RGBA"
    clean = Image.new(mode, frame.size)
    clean.paste(frame.convert(mode))
    return clean


def _sanitize_pdf(source: Path, target: Path) -> None:
    try:
        original = fitz.open(source)
    except Exception as error:
        raise AttachmentRejected("invalid_pdf") from error
    try:
        if original.needs_pass or original.page_count < 1:
            raise AttachmentRejected("invalid_pdf")
        if original.page_count > MAX_PDF_PAGES:
            raise AttachmentRejected("too_many_pdf_pages")
        clean = fitz.open()
        pixels = 0
        try:
            for page in original:
                scale = min(2.0, 3000 / max(page.rect.width, page.rect.height, 1))
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                pixels += pixmap.width * pixmap.height
                if pixels > MAX_PDF_PIXELS:
                    raise AttachmentRejected("pdf_pixel_budget_exceeded")
                clean_page = clean.new_page(width=page.rect.width, height=page.rect.height)
                clean_page.insert_image(clean_page.rect, pixmap=pixmap)
            clean.set_metadata({})
            clean.save(target, garbage=4, clean=True, deflate=True)
        finally:
            clean.close()
    finally:
        original.close()


def _sanitize_text(source: Path, target: Path) -> None:
    target.write_text(_read_valid_text(source), encoding="utf-8", newline="")


def _read_valid_text(source: Path) -> str:
    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeError as error:
        raise AttachmentRejected("invalid_text") from error
    if "\x00" in text:
        raise AttachmentRejected("invalid_text")
    return text


def _sanitize_media(source: Path, target: Path, media_type: str) -> None:
    probe = _probe(source)
    try:
        duration = float(probe.get("format", {}).get("duration", "nan"))
    except (TypeError, ValueError) as error:
        raise AttachmentRejected("invalid_media_duration") from error
    if not 0 < duration <= MAX_MEDIA_SECONDS:
        raise AttachmentRejected("media_duration_exceeded")
    suffix, codec_arguments = _media_codec(media_type)
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory) / f"sanitized{suffix}"
        command = [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(source),
            *codec_arguments,
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-sn",
            "-dn",
            str(temporary),
        ]
        result = subprocess.run(command, capture_output=True, timeout=360, check=False)
        if result.returncode != 0 or not temporary.is_file():
            raise AttachmentRejected("invalid_media")
        sanitized = _probe(temporary)
        sanitized_duration = float(sanitized.get("format", {}).get("duration", "nan"))
        if not 0 < sanitized_duration <= MAX_MEDIA_SECONDS + 1:
            raise AttachmentRejected("invalid_sanitized_media")
        shutil.move(temporary, target)


def _media_codec(media_type: str) -> tuple[str, list[str]]:
    return {
        "audio/mpeg": (".mp3", ["-map", "0:a:0", "-vn", "-c:a", "libmp3lame", "-b:a", "192k"]),
        "audio/mp4": (".m4a", ["-map", "0:a:0", "-vn", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]),
        "audio/ogg": (".ogg", ["-map", "0:a:0", "-vn", "-c:a", "libopus", "-b:a", "128k"]),
        "video/mp4": (".mp4", ["-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"]),
        "video/webm": (".webm", ["-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libvpx-vp9", "-deadline", "good", "-cpu-used", "4", "-crf", "32", "-b:v", "0", "-c:a", "libopus", "-b:a", "128k"]),
    }[media_type]


def _probe(path: Path) -> ProbeResult:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height,channels,sample_rate",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise AttachmentRejected("invalid_media")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AttachmentRejected("invalid_media_probe") from error
    if not isinstance(value, dict):
        raise AttachmentRejected("invalid_media_probe")
    streams = value.get("streams", [])
    media_format = value.get("format", {})
    if not isinstance(streams, list) or not all(isinstance(item, dict) for item in streams):
        raise AttachmentRejected("invalid_media_probe")
    if not isinstance(media_format, dict):
        raise AttachmentRejected("invalid_media_probe")
    return cast(ProbeResult, value)
