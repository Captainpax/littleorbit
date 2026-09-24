"""Weekly theme and reviewed-retrieval boundary tests."""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from little_orbit_ai.knowledge import corpus_revision, load_knowledge_chunks
from little_orbit_ai.prompt import build_prompt, build_week_plan_prompt
from little_orbit_ai.schemas import DayTheme, WeeklyThemePlan


def _plan(*, observances: int = 2, duplicate_title: bool = False) -> WeeklyThemePlan:
    monday = date(2026, 9, 28)
    days = [
        DayTheme(
            date=monday + timedelta(days=index),
            title="Day 0" if duplicate_title and index == 1 else f"Day {index}",
            summary=f"A distinct and inclusive conversation focus for day {index}.",
            observance=f"Observance {index}" if index < observances else None,
        )
        for index in range(7)
    ]
    return WeeklyThemePlan(
        schema_version="1",
        week_start=monday,
        arc_title="Small acts, shared meaning",
        arc_summary="A gentle progression from everyday attention to shared intention.",
        days=days,
    )


def test_week_plan_requires_seven_unique_days_and_at_most_two_observances() -> None:
    assert len(_plan().days) == 7
    with pytest.raises(ValidationError):
        _plan(observances=3)
    with pytest.raises(ValidationError):
        _plan(duplicate_title=True)


def test_retrieval_manifest_loads_only_bounded_package_markdown() -> None:
    chunks = load_knowledge_chunks()

    assert chunks
    assert all(item.document_path.startswith("knowledge/") for item in chunks)
    assert all(item.document_path.endswith(".md") for item in chunks)
    assert all(len(item.body) <= 512 for item in chunks)
    assert len(corpus_revision(chunks)) == 64


def test_generation_and_planning_prompts_bound_untrusted_context() -> None:
    values = [f"source-{index}: " + "x" * 500 for index in range(12)]
    day = DayTheme(
        date=date(2026, 9, 28),
        title="Everyday constellations",
        summary="Notice the small moments that make ordinary time feel shared.",
    )

    prompt = build_prompt(day.date, [], public_context=values, day_theme=day, knowledge=values)
    planning = build_week_plan_prompt(day.date, None, values, values, "en-US")

    assert "source-5" in prompt and "source-6" not in prompt
    assert "source-7" in planning and "source-8" not in planning
    assert "Everyday constellations" in prompt
