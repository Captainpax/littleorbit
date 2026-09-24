"""Code-reviewed Markdown retrieval corpus; generic repository docs never enter prompts."""

import hashlib
import json
import re
from dataclasses import dataclass
from importlib.resources import files


@dataclass(frozen=True)
class KnowledgeChunk:
    """One bounded public writing-guidance chunk ready for local embedding."""

    document_key: str
    document_path: str
    revision_digest: str
    index: int
    body: str


def load_knowledge_chunks() -> list[KnowledgeChunk]:
    """Load only paths declared by the package-owned allowlist manifest."""

    root = files("little_orbit_ai")
    manifest = json.loads(root.joinpath("knowledge_manifest.json").read_text(encoding="utf-8"))
    chunks: list[KnowledgeChunk] = []
    for document in manifest["documents"]:
        key = str(document["key"])
        path = str(document["path"])
        text = root.joinpath(*path.split("/")).read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode()).hexdigest()
        chunks.extend(
            KnowledgeChunk(key, path, digest, index, body)
            for index, body in enumerate(_chunk_markdown(text))
        )
    return chunks


def corpus_revision(chunks: list[KnowledgeChunk]) -> str:
    """Return one stable digest for the exact reviewed corpus revisions."""

    identities = sorted({f"{item.document_key}:{item.revision_digest}" for item in chunks})
    return hashlib.sha256("\n".join(identities).encode()).hexdigest()


def lexical_context(query: str, chunks: list[KnowledgeChunk], limit: int = 6) -> list[str]:
    """Provide deterministic reviewed guidance when semantic retrieval is unavailable."""

    terms = set(re.findall(r"[a-z]{3,}", query.casefold()))
    ranked = sorted(
        chunks,
        key=lambda item: (
            -len(terms.intersection(re.findall(r"[a-z]{3,}", item.body.casefold()))),
            item.document_key,
            item.index,
        ),
    )
    return [item.body for item in ranked[:limit]]


def _chunk_markdown(text: str) -> list[str]:
    """Join paragraph blocks without exceeding the embedding transport's 512-char limit."""

    paragraphs = [re.sub(r"\s+", " ", item).strip() for item in text.split("\n\n")]
    output: list[str] = []
    current = ""
    for paragraph in filter(None, paragraphs):
        candidate = f"{current} {paragraph}".strip()
        if current and len(candidate) > 480:
            output.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        output.append(current)
    if any(len(item) > 512 for item in output):
        raise ValueError("reviewed knowledge paragraph exceeds the embedding bound")
    return output
