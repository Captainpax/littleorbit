"""Versioned prompt construction with an explicit zero-user-data boundary."""

from datetime import date

PROMPT_VERSION = "question-batch-v2"


def build_prompt(target_date: date, recent_questions: list[str]) -> str:
    """Build a bounded prompt using only public generation context."""

    # Only recent site-wide public questions cross the model boundary. Bounding both
    # count and length keeps context predictable and prevents this parameter from
    # becoming a path for user, couple, or other private data.
    recent = "\n".join(f"- {item[:240]}" for item in recent_questions[-60:]) or "- none"
    return f"""You write warm daily questions for Little Orbit, a private adult couples app.
Return JSON only for schema version 2 and calendar date {target_date.isoformat()}.

Create exactly 10 candidates: exactly 8 general questions and exactly 2 optional,
non-graphic intimacy questions. Use at least four interaction kinds and four categories.
Every prompt must be a natural question ending in ?. It must help two partners learn about
each other without needing any private context. Prefer specific, conversational wording.

Interaction rules:
- single_choice and multiple_choice: 2-6 short answer options.
- free_text: no options.
- partner_guess: ask what the respondent themselves would choose. The app separately asks
  them to guess their partner's choice from the same options. Never phrase it as an ordinary
  guess about a partner.
- weighted_choice: 2-5 things to rate independently from 1-5, plus short low/high labels
  appropriate to that prompt. Never mention a 1-10 scale.
- Give every option one icon from: heart, chat, home, meal, movie, music, outdoors, play,
  rest, star, travel, surprise. Free-text questions use empty option and icon arrays.
- Non-weighted questions use null scale labels.

Use a warm balance of everyday, playful, memories, dreams, values, and connection. Start
light and include meaningful prompts without therapy, judgment, pressure, or a scoreboard.
Intimacy prompts must be optional, consent-centered, non-graphic, and answerable with comfort.
Never ask for identity, contact details, secrets, precise location, diagnosis, medical/legal/
financial advice, coercion, manipulation, self-harm, minors, or graphic sexual content.

Avoid recent ideas and wording:
{recent}

Output keys: schema_version, date, questions. Every question has client_id, kind, prompt,
category, intimacy, options, option_icons, scale_low_label, scale_high_label. Use lowercase
client_id values of 3-48 letters, numbers, or hyphens. Do not add markdown or commentary."""
