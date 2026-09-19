"""Question generation, quarantine, selection, and curated fallback pipeline."""

import json
from dataclasses import dataclass
from datetime import date
from importlib.resources import files
from itertools import combinations

from .ollama import OllamaClient, OllamaFailure, OllamaSettings, ParsedBatch
from .prompt import PROMPT_VERSION, build_prompt
from .safety import validate_candidate
from .schemas import CandidateQuestion, Category, PublishedPool, QuestionKind


@dataclass(frozen=True)
class QuarantinedCandidate:
    """Rejected public candidate and deterministic reason codes."""

    client_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PipelineResult:
    """Publishable pool accompanied by quarantine evidence."""

    pool: PublishedPool
    quarantined: tuple[QuarantinedCandidate, ...]


def load_curated_bank() -> list[CandidateQuestion]:
    """Load the bundled, human-reviewed offline question bank."""

    content = files("little_orbit_ai").joinpath("bank.json").read_text(encoding="utf-8")
    return [CandidateQuestion.model_validate(item) for item in json.loads(content)]


def select_pool(
    target_date: date,
    batch: ParsedBatch | None,
    recent_questions: list[str],
    settings: OllamaSettings,
    failure_reason: str | None,
    curated_bank: list[CandidateQuestion] | None = None,
) -> PipelineResult:
    """Validate candidates and deterministically fill shortages from the curated bank."""

    accepted: list[CandidateQuestion] = []
    # Structural failures from parsing remain quarantined alongside later content
    # failures, while valid siblings can still contribute to the publishable pool.
    quarantined = [
        QuarantinedCandidate(item.client_id, item.reasons)
        for item in (batch.quarantined if batch else ())
    ]
    seen = list(recent_questions)
    for candidate in batch.questions if batch else []:
        result = validate_candidate(candidate, seen)
        if result.accepted:
            accepted.append(candidate)
            # Extend the comparison set as candidates pass so one model batch cannot
            # publish multiple versions of the same idea.
            seen.append(candidate.prompt)
        else:
            quarantined.append(QuarantinedCandidate(candidate.client_id, result.reasons))

    generated_general = [item for item in accepted if not item.intimacy]
    intimacy = [item for item in accepted if item.intimacy]
    used_ids = {item.client_id for item in accepted}
    curated = curated_bank or load_curated_bank()
    bank = [item for item in curated if not item.intimacy]
    # Calendar-based rotation spreads fallback usage without randomness, preserving
    # reproducibility for evaluation and incident review.
    start = (target_date.toordinal() * 5) % len(bank)
    ordered_bank = bank[start:] + bank[:start]
    general = list(generated_general)
    for bank_item in ordered_bank:
        # Selection examines five-item combinations, so cap the validated pool to
        # keep that search bounded while retaining ample room for variety.
        if len(general) >= 14:
            break
        # Revalidate the human-reviewed bank at use time so fallback never bypasses
        # the same current safety and duplicate rules applied to model output.
        validation = validate_candidate(bank_item, recent_questions)
        if (
            validation.accepted
            and bank_item.client_id not in used_ids
            and bank_item.prompt not in recent_questions
        ):
            general.append(bank_item)
            used_ids.add(bank_item.client_id)
    if len(general) < 5:
        raise RuntimeError("curated bank invariant failed: fewer than five general questions")
    missing_generated_intimacy = not intimacy
    if missing_generated_intimacy:
        # Intimacy remains a separate optional pool; it never fills one of the five
        # required general-question positions.
        intimacy_bank = [item for item in curated if item.intimacy]
        intimacy = [intimacy_bank[target_date.toordinal() % len(intimacy_bank)]]
    if (
        failure_reason is None
        and batch
        and (
            len([item for item in accepted if not item.intimacy]) < 5
            or missing_generated_intimacy
        )
    ):
        # A successful model call can still require fallback after deterministic
        # validation; record that degraded result distinctly from transport failure.
        failure_reason = "insufficient_valid_candidates"
    selected = _balanced_five(general, {item.client_id for item in generated_general})
    pool = PublishedPool(
        date=target_date,
        general=selected,
        intimacy_alternatives=intimacy,
        prompt_version=PROMPT_VERSION,
        model=settings.model,
        model_manifest_digest=settings.manifest_digest,
        fallback_reason=failure_reason,
    )
    return PipelineResult(pool, tuple(quarantined))


def _balanced_five(
    candidates: list[CandidateQuestion], generated_ids: set[str]
) -> list[CandidateQuestion]:
    """Choose a warm, varied set deterministically from a small validated pool."""

    best: tuple[int, tuple[CandidateQuestion, ...]] | None = None
    # Exhaustive scoring is deterministic and remains cheap because select_pool
    # deliberately limits this input to fourteen candidates.
    for group in combinations(candidates[:14], 5):
        kinds = {item.kind for item in group}
        categories = {item.category for item in group}
        kind_counts = [sum(item.kind is kind for item in group) for kind in kinds]
        category_counts = [sum(item.category is category for item in group) for category in categories]
        meaningful = any(
            item.category
            in {Category.CONNECTION, Category.MEMORIES, Category.VALUES, Category.DREAMS}
            for item in group
        )
        light = any(item.category in {Category.EVERYDAY, Category.PLAYFUL} for item in group)
        score = len(kinds) * 20 + len(categories) * 16
        score += sum(item.client_id in generated_ids for item in group) * 2
        score += 15 if meaningful else 0
        score += 15 if light else 0
        score -= sum(max(count - 2, 0) * 40 for count in kind_counts + category_counts)
        # Client IDs provide a stable tie-breaker, avoiding process- or hash-order
        # changes in which equally diverse pool is published.
        key = tuple(item.client_id for item in group)
        candidate = (score, group)
        if best is None or score > best[0] or (score == best[0] and key < tuple(i.client_id for i in best[1])):
            best = candidate
    if best is None:
        raise RuntimeError("validated question pool contains fewer than five questions")
    return _order_for_conversation(list(best[1]))


def _order_for_conversation(items: list[CandidateQuestion]) -> list[CandidateQuestion]:
    """Put lighter taps first and more reflective prompts near the end."""

    # Explicit ranks make the intended emotional progression independent of enum
    # declaration order or serialized values shared with clients.
    category_rank = {
        Category.PLAYFUL: 0,
        Category.EVERYDAY: 1,
        Category.DREAMS: 2,
        Category.MEMORIES: 3,
        Category.VALUES: 4,
        Category.CONNECTION: 5,
        Category.INTIMACY: 6,
    }
    kind_rank = {
        QuestionKind.SINGLE: 0,
        QuestionKind.MULTIPLE: 1,
        QuestionKind.WEIGHTED: 2,
        QuestionKind.PARTNER_GUESS: 3,
        QuestionKind.FREE_TEXT: 4,
    }
    return sorted(items, key=lambda item: (category_rank[item.category], kind_rank[item.kind]))


async def generate_pool(
    target_date: date,
    recent_questions: list[str],
    client: OllamaClient,
    settings: OllamaSettings,
    curated_bank: list[CandidateQuestion] | None = None,
) -> PipelineResult:
    """Generate once within a deadline, then always return five general questions."""

    # Do not retry model generation here: one bounded attempt prevents an outage from
    # delaying the daily pool, and deterministic fallback guarantees coverage.
    try:
        batch = await client.generate(build_prompt(target_date, recent_questions))
        if batch.date != target_date:
            return select_pool(
                target_date,
                None,
                recent_questions,
                settings,
                "wrong_calendar_date",
                curated_bank,
            )
        return select_pool(target_date, batch, recent_questions, settings, None, curated_bank)
    except OllamaFailure:
        return select_pool(
            target_date,
            None,
            recent_questions,
            settings,
            "ollama_unavailable",
            curated_bank,
        )
