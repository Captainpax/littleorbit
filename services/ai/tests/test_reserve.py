"""One-year reserve count, safety, review, and uniqueness contracts."""

from little_orbit_ai.reserve import GENERAL_COUNT, INTIMACY_COUNT, load_reviewed_reserve
from little_orbit_ai.safety import validate_candidate


def test_reviewed_reserve_has_exact_one_year_capacity() -> None:
    entries = load_reviewed_reserve()

    general = [item for item in entries if not item.candidate.intimacy]
    intimacy = [item for item in entries if item.candidate.intimacy]
    assert len(general) == GENERAL_COUNT == 1_825
    assert len(intimacy) == INTIMACY_COUNT == 365
    assert all(item.review_tier == "intimacy-reviewed" for item in intimacy)
    assert sum(item.review_tier == "sample-reviewed" for item in general) == 365


def test_reviewed_reserve_has_no_repeated_words_or_concepts() -> None:
    entries = load_reviewed_reserve()

    assert len({item.content_hash for item in entries}) == len(entries)
    assert len({item.candidate.concept_family for item in entries}) == len(entries)
    assert all(validate_candidate(item.candidate, []).accepted for item in entries)


def test_each_general_selection_window_is_distinct_and_varied() -> None:
    general = [
        item.candidate for item in load_reviewed_reserve() if not item.candidate.intimacy
    ]

    wrapped = general + general[:14]
    for start in range(0, len(general), 5):
        window = wrapped[start : start + 14]
        assert len({item.concept_family for item in window}) == len(window)
        assert len({item.kind for item in window}) >= 4
        assert len({item.category for item in window}) >= 3
