"""Small deterministic evaluation runner for CI and model changes."""

from datetime import date, timedelta

from .ollama import OllamaSettings
from .pipeline import select_pool


def main() -> None:
    """Assert seven-day curated coverage without requiring Ollama or a GPU."""

    start = date.today()
    settings = OllamaSettings()
    for offset in range(7):
        result = select_pool(start + timedelta(days=offset), None, [], settings, "evaluation")
        assert len(result.pool.general) == 5
    print("AI evaluation passed: seven future dates have five safe fallback questions")


if __name__ == "__main__":
    main()
