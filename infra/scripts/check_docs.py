"""Fail when repository-local Markdown links point at missing files."""

import os
import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r"\[[^\]]*\]\((?!https?://|mailto:|#)([^)]+)\)")
IGNORED_DIRECTORIES = {".git", ".gradle", ".inspect", ".next", "build", "node_modules"}


def _documents() -> list[Path]:
    """Find tracked documentation without traversing dependency or build caches."""

    documents: list[Path] = []
    for directory, child_directories, filenames in os.walk(ROOT):
        child_directories[:] = [
            name for name in child_directories if name not in IGNORED_DIRECTORIES
        ]
        documents.extend(
            Path(directory) / name for name in filenames if Path(name).suffix == ".md"
        )
    return documents


def main() -> None:
    """Check every local Markdown target while ignoring optional anchors."""

    missing: list[str] = []
    for document in _documents():
        content = document.read_text(encoding="utf-8")
        for raw_target in LINK.findall(content):
            target = unquote(raw_target.strip("<>").split("#", maxsplit=1)[0])
            if target and not (document.parent / target).resolve().exists():
                missing.append(f"{document.relative_to(ROOT)} -> {target}")
    if missing:
        raise SystemExit("Missing documentation links:\n" + "\n".join(missing))
    print("Documentation links are valid")


if __name__ == "__main__":
    main()
