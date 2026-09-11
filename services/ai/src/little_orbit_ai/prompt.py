"""Versioned prompt construction with an explicit zero-user-data boundary."""

from datetime import date

PROMPT_VERSION = "question-batch-v1"


def build_prompt(target_date: date, recent_questions: list[str]) -> str:
    """Build a bounded prompt using only public generation context."""

    recent = "\n".join(f"- {question[:240]}" for question in recent_questions[-40:]) or "- none"
    return f"""You generate safe, warm daily questions for an adult couples app.
Return JSON only, matching schema version 1. Target calendar date: {target_date.isoformat()}.
Create 10 candidates: at least 7 general and up to 3 optional non-graphic intimacy questions.
Use all supported kinds: single_choice, multiple_choice, free_text, partner_guess, weighted_scale.
Choice kinds need 2-8 short unique options. Other kinds need an empty options array.
Use a lowercase client_id of 3-48 letters, numbers, or hyphens. Allowed categories are:
everyday, memories, dreams, values, playful, connection, and intimacy.
Questions must be answerable, specific, kind, and useful without knowing either person.
Never ask for identifying information, precise location, secrets, diagnosis, medical/legal/financial
advice, coercion, manipulation, self-harm, minors, or graphic sexual content. Intimacy questions
must stay optional and consent-centered. Do not repeat recent wording:
{recent}

Output object keys: schema_version, date, questions. Question keys: client_id, kind, prompt,
category, intimacy, options. Do not include markdown or commentary."""
