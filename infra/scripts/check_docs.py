"""Validate the repository Markdown inventory and local links."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "docs" / "DOCUMENTATION-MAP.md"
EXCLUDED_PARTS = frozenset(
    {
        ".codex-remote-attachments",
        ".git",
        ".gradle",
        ".inspect",
        ".pytest_cache",
        ".venv",
        ".venv313",
        "build",
        "node_modules",
    }
)
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
INVENTORY = re.compile(r"^- `([^`]+\.md)`", re.MULTILINE)


def markdown_files() -> set[str]:
    """Return repository-relative Markdown paths owned by the project."""

    return {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*.md")
        if not EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)
    }


def inventory_files() -> set[str]:
    """Read paths only from the explicitly delimited documentation inventory."""

    text = MAP.read_text(encoding="utf-8")
    start = text.index("<!-- documentation-inventory:start -->")
    end = text.index("<!-- documentation-inventory:end -->")
    return set(INVENTORY.findall(text[start:end]))


def broken_links(files: set[str]) -> list[str]:
    """Return missing local Markdown link targets with their source files."""

    failures: list[str] = []
    for relative in sorted(files):
        source = ROOT / relative
        for raw in LINK.findall(source.read_text(encoding="utf-8")):
            target = raw.strip().strip("<>").split("#", 1)[0]
            if not target or "://" in target or target.startswith(("mailto:", "/")):
                continue
            resolved = (source.parent / unquote(target)).resolve()
            if not resolved.exists():
                failures.append(f"{relative}: missing link target {target}")
    return failures


def main() -> int:
    """Report inventory drift and broken local links without changing files."""

    actual = markdown_files()
    listed = inventory_files()
    failures = [f"unlisted Markdown: {path}" for path in sorted(actual - listed)]
    failures.extend(f"missing listed Markdown: {path}" for path in sorted(listed - actual))
    failures.extend(broken_links(actual))
    if failures:
        print("\n".join(failures))
        return 1
    print(f"Documentation inventory and local links are valid ({len(actual)} files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
