"""Question generation, quarantine, selection, and curated fallback pipeline."""

import json
from dataclasses import dataclass
from datetime import date
from importlib.resources import files

from .ollama import OllamaClient, OllamaFailure, OllamaSettings
from .prompt import PROMPT_VERSION, build_prompt
from .safety import validate_candidate
from .schemas import CandidateQuestion, GeneratedBatch, PublishedPool


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
    batch: GeneratedBatch | None,
    recent_questions: list[str],
    settings: OllamaSettings,
    failure_reason: str | None,
    curated_bank: list[CandidateQuestion] | None = None,
) -> PipelineResult:
    """Validate candidates and deterministically fill shortages from the curated bank."""

    accepted: list[CandidateQuestion] = []
    quarantined: list[QuarantinedCandidate] = []
    seen = list(recent_questions)
    for candidate in batch.questions if batch else []:
        result = validate_candidate(candidate, seen)
        if result.accepted:
            accepted.append(candidate)
            seen.append(candidate.prompt)
        else:
            quarantined.append(QuarantinedCandidate(candidate.client_id, result.reasons))

    general = [item for item in accepted if not item.intimacy]
    intimacy = [item for item in accepted if item.intimacy]
    used_ids = {item.client_id for item in accepted}
    curated = curated_bank or load_curated_bank()
    bank = [item for item in curated if not item.intimacy]
    start = (target_date.toordinal() * 5) % len(bank)
    ordered_bank = bank[start:] + bank[:start]
    for bank_item in ordered_bank:
        if len(general) >= 5:
            break
        if bank_item.client_id not in used_ids and bank_item.prompt not in recent_questions:
            general.append(bank_item)
            used_ids.add(bank_item.client_id)
    if len(general) < 5:
        raise RuntimeError("curated bank invariant failed: fewer than five general questions")
    if not intimacy:
        intimacy_bank = [item for item in curated if item.intimacy]
        intimacy = [intimacy_bank[target_date.toordinal() % len(intimacy_bank)]]
    if (
        failure_reason is None
        and batch
        and len([item for item in accepted if not item.intimacy]) < 5
    ):
        failure_reason = "insufficient_valid_candidates"
    pool = PublishedPool(
        date=target_date,
        general=general[:5],
        intimacy_alternatives=intimacy,
        prompt_version=PROMPT_VERSION,
        model=settings.model,
        model_manifest_digest=settings.manifest_digest,
        fallback_reason=failure_reason,
    )
    return PipelineResult(pool, tuple(quarantined))


async def generate_pool(
    target_date: date,
    recent_questions: list[str],
    client: OllamaClient,
    settings: OllamaSettings,
    curated_bank: list[CandidateQuestion] | None = None,
) -> PipelineResult:
    """Generate once within a deadline, then always return five general questions."""

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
