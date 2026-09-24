"""Fail fast when one Little Orbit 1.3 release surface drifts."""

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _expect(actual: str, expected: str, source: str) -> None:
    if actual != expected:
        raise SystemExit(f"{source} is {actual!r}; expected {expected!r}")


def _quoted(path: Path, pattern: str, source: str) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    if match is None:
        raise SystemExit(f"{source} version was not found")
    return match.group(1)


def main() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    train = json.loads((ROOT / "protocol/release-train.json").read_text(encoding="utf-8"))
    _expect(str(train["release_train"]), version, "release train")
    _expect(str(train["little_orbit_version"]), version, "Little Orbit contract")
    _expect(str(train["big_orbit_version"]), version, "Big Orbit contract")
    root_gradle = ROOT / "build.gradle.kts"
    _expect(_quoted(root_gradle, r'^version = "([^"]+)"', "Gradle"), version, "Gradle")
    _expect(
        _quoted(root_gradle, r'littleOrbitVersionName"\] = "([^"]+)"', "phone"),
        version,
        "phone",
    )
    _expect(
        _quoted(root_gradle, r'littleOrbitWearVersionName"\] = "([^"]+)"', "Wear"),
        version,
        "Wear",
    )
    for relative in ("services/api/pyproject.toml", "services/ai/pyproject.toml"):
        project = tomllib.loads((ROOT / relative).read_text(encoding="utf-8"))["project"]
        _expect(str(project["version"]), version, relative)
    package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "apps/web/package-lock.json").read_text(encoding="utf-8"))
    _expect(str(package["version"]), version, "web package")
    _expect(str(lock["version"]), version, "web lock")
    print(f"Little Orbit release train {version} is internally consistent.")


if __name__ == "__main__":
    main()
