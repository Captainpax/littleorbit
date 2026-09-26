"""Deterministic, code-reviewed one-year quiz reserve.

The reserve is assembled from bounded editorial components rather than model output.
Every context/lens pair owns a distinct concept identity, and each generated prompt
still passes the ordinary safety and duplicate gates before it can be published.
"""

from dataclasses import dataclass

from .safety import normalized_hash, validate_candidate
from .schemas import CandidateQuestion, Category, IconKey, QuestionKind

BANK_VERSION = 1
GENERAL_COUNT = 1_825
INTIMACY_COUNT = 365


@dataclass(frozen=True)
class Lens:
    """One reviewed conversational purpose applied to many concrete contexts."""

    key: str
    prompt: str
    summary: str
    category: Category
    kind: QuestionKind = QuestionKind.FREE_TEXT
    options: tuple[str, ...] = ()
    icons: tuple[IconKey, ...] = ()


@dataclass(frozen=True)
class ReserveEntry:
    """Immutable publishable candidate plus its editorial-review tier."""

    candidate: CandidateQuestion
    review_tier: str
    content_hash: str


CONTEXTS: tuple[tuple[str, str, str], ...] = (
    ("slow-morning", "a slow morning with no fixed agenda", "everyday"),
    ("busy-morning", "a morning when both of you have a lot to do", "support"),
    ("shared-breakfast", "sharing breakfast or a first meal of the day", "rituals"),
    ("midday-pause", "finding a small pause in the middle of the day", "rest"),
    ("long-day", "reconnecting after a long day", "support"),
    ("quiet-evening", "a quiet evening with room to unwind", "rest"),
    ("late-night-talk", "a late-night conversation when the world feels quieter", "connection"),
    ("weekend-opening", "the first open stretch of a weekend", "play"),
    ("sunday-reset", "resetting gently before a new week", "rituals"),
    ("shared-meal", "planning or enjoying a meal together", "everyday"),
    ("new-recipe", "trying a recipe neither of you knows well", "novelty"),
    ("favorite-takeout", "returning to a favorite easy meal", "comfort"),
    ("grocery-run", "turning an ordinary grocery run into shared time", "everyday"),
    ("household-task", "handling a routine task that needs teamwork", "teamwork"),
    ("tidy-space", "making one shared or visited space feel calmer", "home"),
    ("small-repair", "figuring out a small practical problem together", "teamwork"),
    ("errand-day", "moving through a day of necessary errands", "everyday"),
    ("waiting-time", "waiting together when plans are briefly on hold", "patience"),
    ("commute", "checking in around a tiring commute or trip home", "support"),
    ("weather-change", "noticing a sudden change in the weather", "seasons"),
    ("rainy-day", "a rainy day that changes the original plan", "adaptability"),
    ("sunny-hour", "an unexpectedly beautiful hour outside", "joy"),
    ("first-cold-day", "the first truly cold day of a season", "seasons"),
    ("warm-night", "a warm evening that invites a slower pace", "seasons"),
    ("season-turn", "the feeling of one season turning into another", "change"),
    ("short-walk", "taking a short walk with nowhere urgent to be", "outdoors"),
    ("new-route", "choosing a route or neighborhood that feels new", "novelty"),
    ("nature-stop", "pausing to notice something in nature", "outdoors"),
    ("city-wander", "wandering through a lively public place", "adventure"),
    ("scenic-drive", "sharing a drive or ride with time to look around", "adventure"),
    ("travel-plan", "imagining a future day trip or journey", "dreams"),
    ("travel-delay", "adapting together when travel does not go to plan", "adaptability"),
    ("arrival", "arriving somewhere after looking forward to it", "anticipation"),
    ("return-home", "returning to familiar surroundings after time away", "home"),
    ("long-distance-call", "making a call feel close while physically apart", "distance"),
    ("voice-message", "sending a voice message that brightens the day", "distance"),
    ("reunion", "seeing each other again after meaningful time apart", "connection"),
    ("movie-choice", "choosing something to watch together", "play"),
    ("music-share", "sharing a song or piece of music", "music"),
    ("game-night", "playing an easygoing game together", "play"),
    ("creative-hour", "making or learning something creative side by side", "creativity"),
    ("book-story", "sharing a story, article, or book idea", "curiosity"),
    ("photo-memory", "coming across a photo from another time", "memories"),
    ("old-song", "hearing a song connected to an earlier chapter", "memories"),
    ("shared-first", "remembering one of your shared first experiences", "memories"),
    ("tiny-tradition", "returning to a tiny tradition that belongs to you both", "rituals"),
    ("celebration", "marking a win or meaningful milestone", "celebration"),
    ("ordinary-anniversary", "noticing an ordinary date with a shared story", "memories"),
    ("gift-idea", "thinking of a small gesture with no occasion required", "care"),
    ("surprise-plan", "planning a welcome, easygoing surprise", "play"),
    ("good-news", "sharing news that brings real excitement", "joy"),
    ("disappointment", "being together after something disappointing", "support"),
    ("uncertain-choice", "facing a choice without a clearly perfect answer", "values"),
    ("changed-plan", "adjusting when a shared plan needs to change", "adaptability"),
    ("misunderstanding", "reconnecting after a small misunderstanding", "repair"),
    ("hard-conversation", "making room for a conversation that feels important", "communication"),
    ("apology", "repairing after one of you wants to apologize", "repair"),
    ("forgiveness", "letting a repaired moment become lighter over time", "repair"),
    ("stressful-week", "supporting each other through a stressful week", "support"),
    ("low-energy-day", "sharing time when energy is limited", "rest"),
    ("sick-day", "offering care during a minor sick day", "care"),
    ("big-task", "starting a task that feels bigger than expected", "teamwork"),
    ("finished-task", "enjoying the relief after finishing something together", "teamwork"),
    ("money-free-fun", "finding something enjoyable that costs nothing", "play"),
    ("screen-free-hour", "spending an hour with screens set aside", "presence"),
    ("unexpected-free-time", "discovering that an hour has opened up unexpectedly", "joy"),
    ("future-home", "imagining what a comforting future home base could feel like", "dreams"),
    ("future-tradition", "inventing a tradition for a future chapter", "dreams"),
    ("next-month", "looking ahead to the next month without overplanning it", "dreams"),
    ("five-years", "imagining a hopeful detail several years from now", "dreams"),
    ("community-moment", "taking part in a welcoming community moment", "belonging"),
    ("helping-others", "doing something kind for people beyond your relationship", "values"),
    ("gratitude-pause", "pausing to notice what feels quietly good right now", "gratitude"),
)


LENSES: tuple[Lens, ...] = (
    Lens(
        "tiny-joy",
        "What small detail could make {context} unexpectedly delightful?",
        "A small source of shared delight",
        Category.PLAYFUL,
    ),
    Lens(
        "appreciation",
        "What would you enjoy appreciating about each other during {context}?",
        "An opportunity for specific appreciation",
        Category.CONNECTION,
    ),
    Lens(
        "curiosity",
        "What would you be curious to learn about each other during {context}?",
        "A fresh point of mutual curiosity",
        Category.CONNECTION,
    ),
    Lens(
        "memory",
        "What earlier shared memory might {context} bring to mind for you?",
        "A context-linked shared memory",
        Category.MEMORIES,
    ),
    Lens(
        "future",
        "What future possibility could {context} inspire you to imagine together?",
        "A hopeful future possibility",
        Category.DREAMS,
    ),
    Lens(
        "pace",
        "During {context}, which pace would feel best to you?",
        "A preferred shared pace",
        Category.EVERYDAY,
        QuestionKind.SINGLE,
        ("Unhurried", "Steady", "Spontaneous", "Flexible"),
        (IconKey.REST, IconKey.HOME, IconKey.SURPRISE, IconKey.TRAVEL),
    ),
    Lens(
        "attention",
        "During {context}, which kind of attention would help you feel most present?",
        "A preferred form of attention",
        Category.CONNECTION,
        QuestionKind.SINGLE,
        ("Quiet listening", "Shared laughter", "Practical help", "Gentle affection"),
        (IconKey.CHAT, IconKey.PLAY, IconKey.HOME, IconKey.HEART),
    ),
    Lens(
        "energy",
        "During {context}, which energy would you personally choose first?",
        "A self-answerable energy preference",
        Category.PLAYFUL,
        QuestionKind.PARTNER_GUESS,
        ("Cozy", "Playful", "Curious", "Peaceful"),
        (IconKey.REST, IconKey.PLAY, IconKey.STAR, IconKey.HOME),
    ),
    Lens(
        "role",
        "During {context}, which role would you personally enjoy taking first?",
        "A self-answerable teamwork role",
        Category.VALUES,
        QuestionKind.PARTNER_GUESS,
        ("Planner", "Cheerleader", "Explorer", "Calm anchor"),
        (IconKey.CHAT, IconKey.STAR, IconKey.TRAVEL, IconKey.HEART),
    ),
    Lens(
        "comfort",
        "During {context}, which comfort would feel most welcome?",
        "A preferred source of comfort",
        Category.EVERYDAY,
        QuestionKind.SINGLE,
        ("Warm words", "A snack", "Quiet company", "A change of scene"),
        (IconKey.CHAT, IconKey.MEAL, IconKey.REST, IconKey.OUTDOORS),
    ),
    Lens(
        "signals",
        "During {context}, which signals of care would you notice most?",
        "Recognizable signals of care",
        Category.CONNECTION,
        QuestionKind.MULTIPLE,
        ("Checking in", "Making space", "Helping out", "Sharing humor"),
        (IconKey.CHAT, IconKey.REST, IconKey.HOME, IconKey.PLAY),
    ),
    Lens(
        "ingredients",
        "Which ingredients could make {context} feel more like quality time?",
        "Ingredients for quality time",
        Category.EVERYDAY,
        QuestionKind.MULTIPLE,
        ("No rushing", "A shared choice", "Something tasty", "A little novelty"),
        (IconKey.REST, IconKey.CHAT, IconKey.MEAL, IconKey.SURPRISE),
    ),
    Lens(
        "play",
        "Which playful touches could add warmth to {context}?",
        "Easygoing playful additions",
        Category.PLAYFUL,
        QuestionKind.MULTIPLE,
        ("An inside joke", "A tiny challenge", "Music", "A surprise"),
        (IconKey.PLAY, IconKey.STAR, IconKey.MUSIC, IconKey.SURPRISE),
    ),
    Lens(
        "support",
        "Which kinds of support could help during {context}?",
        "Useful forms of mutual support",
        Category.CONNECTION,
        QuestionKind.MULTIPLE,
        ("Listen first", "Help decide", "Take one task", "Offer encouragement"),
        (IconKey.CHAT, IconKey.STAR, IconKey.HOME, IconKey.HEART),
    ),
    Lens(
        "meaning",
        "Which values could {context} express for you?",
        "Values expressed through an ordinary context",
        Category.VALUES,
        QuestionKind.MULTIPLE,
        ("Care", "Adventure", "Patience", "Teamwork"),
        (IconKey.HEART, IconKey.TRAVEL, IconKey.REST, IconKey.HOME),
    ),
    Lens(
        "talk",
        "What conversation would make {context} feel more meaningful?",
        "A meaningful conversation opening",
        Category.CONNECTION,
    ),
    Lens(
        "learn",
        "What could {context} teach you about how you work as a pair?",
        "A shared-learning reflection",
        Category.VALUES,
    ),
    Lens(
        "notice",
        "What might you notice about yourself during {context}?",
        "Self-awareness that can be shared",
        Category.VALUES,
    ),
    Lens(
        "wish",
        "What gentle wish would you bring into {context}?",
        "A gentle personal wish",
        Category.DREAMS,
    ),
    Lens(
        "story",
        "What story would you want to remember from {context}?",
        "A story worth carrying forward",
        Category.MEMORIES,
    ),
    Lens(
        "connection-weight",
        "During {context}, how much could each choice help you feel connected?",
        "Relative connection value of shared choices",
        Category.CONNECTION,
        QuestionKind.WEIGHTED,
        ("Talk openly", "Laugh together", "Share a task", "Rest nearby"),
        (IconKey.CHAT, IconKey.PLAY, IconKey.HOME, IconKey.REST),
    ),
    Lens(
        "joy-weight",
        "During {context}, how much could each idea add a little joy?",
        "Relative joy value of simple ideas",
        Category.PLAYFUL,
        QuestionKind.WEIGHTED,
        ("Music", "A treat", "Fresh air", "A game"),
        (IconKey.MUSIC, IconKey.MEAL, IconKey.OUTDOORS, IconKey.PLAY),
    ),
    Lens(
        "care-weight",
        "During {context}, how much could each gesture help you feel cared for?",
        "Relative care value of supportive gestures",
        Category.CONNECTION,
        QuestionKind.WEIGHTED,
        ("A check-in", "Practical help", "Affection", "Quiet space"),
        (IconKey.CHAT, IconKey.HOME, IconKey.HEART, IconKey.REST),
    ),
    Lens(
        "novelty-weight",
        "During {context}, how appealing would each kind of novelty feel?",
        "Relative appetite for novelty",
        Category.DREAMS,
        QuestionKind.WEIGHTED,
        ("New place", "New flavor", "New activity", "New question"),
        (IconKey.TRAVEL, IconKey.MEAL, IconKey.PLAY, IconKey.CHAT),
    ),
    Lens(
        "ritual-weight",
        "During {context}, how meaningful could each tiny ritual become?",
        "Relative meaning of possible rituals",
        Category.VALUES,
        QuestionKind.WEIGHTED,
        ("A greeting", "A shared song", "A photo", "A gratitude pause"),
        (IconKey.HEART, IconKey.MUSIC, IconKey.STAR, IconKey.REST),
    ),
)


INTIMACY_LENSES: tuple[tuple[str, str, str], ...] = (
    (
        "affection",
        "Thinking about affection around {context}, what kind of closeness would feel welcome and comfortable?",
        "A voluntary affection preference",
    ),
    (
        "check-in",
        "Thinking about closeness around {context}, how would you like each other to check in about comfort?",
        "A consent-centered check-in preference",
    ),
    (
        "pause",
        "Thinking about affection around {context}, what signal would make pausing or changing course feel easy?",
        "An easy boundary or pause signal",
    ),
    (
        "atmosphere",
        "Thinking about closeness around {context}, what atmosphere would help you feel relaxed and cared for?",
        "A comfortable atmosphere for closeness",
    ),
    (
        "reconnect",
        "Thinking about affection around {context}, what gentle way of reconnecting would feel good to you?",
        "A gentle and voluntary reconnection preference",
    ),
)


def load_reviewed_reserve() -> list[ReserveEntry]:
    """Build and validate exactly one year of general and intimacy fallback."""

    entries = [*_general_entries(), *_intimacy_entries()]
    if len(entries) != GENERAL_COUNT + INTIMACY_COUNT:
        raise ValueError("reviewed reserve count changed")
    if len({item.candidate.concept_family for item in entries}) != len(entries):
        raise ValueError("reviewed reserve concept identity is not unique")
    if len({item.content_hash for item in entries}) != len(entries):
        raise ValueError("reviewed reserve wording is not unique")
    for entry in entries:
        result = validate_candidate(entry.candidate, [])
        if not result.accepted:
            raise ValueError(f"unsafe reviewed reserve entry: {entry.candidate.client_id}")
    return entries


def reserve_candidates() -> list[CandidateQuestion]:
    """Return candidates in a stable, daily-diverse permutation."""

    return [item.candidate for item in load_reviewed_reserve()]


def _general_entries() -> list[ReserveEntry]:
    entries: list[ReserveEntry] = []
    for index in range(GENERAL_COUNT):
        # 366 is coprime to 1,825 and advances one context plus five lenses,
        # spreading interaction types and categories across every daily window.
        pair = (index * 366) % GENERAL_COUNT
        lens = LENSES[pair // len(CONTEXTS)]
        context_key, context, context_tag = CONTEXTS[pair % len(CONTEXTS)]
        candidate = _candidate(index, context_key, context, context_tag, lens)
        review = "sample-reviewed" if index % 5 == 0 else "template-reviewed"
        entries.append(ReserveEntry(candidate, review, normalized_hash(candidate.prompt)))
    return entries


def _candidate(
    index: int,
    context_key: str,
    context: str,
    context_tag: str,
    lens: Lens,
) -> CandidateQuestion:
    anchors = ("Not much", "Very much") if lens.kind is QuestionKind.WEIGHTED else (None, None)
    return CandidateQuestion(
        client_id=f"r1-g-{index:04d}",
        kind=lens.kind,
        prompt=lens.prompt.format(context=context),
        category=lens.category,
        intimacy=False,
        options=list(lens.options),
        option_icons=list(lens.icons),
        scale_low_label=anchors[0],
        scale_high_label=anchors[1],
        concept_family=f"g-{context_key}-{lens.key}",
        concept_summary=f"{lens.summary} in the context of {context}",
        theme_tags=[context_tag, lens.key],
    )


def _intimacy_entries() -> list[ReserveEntry]:
    entries: list[ReserveEntry] = []
    for index in range(INTIMACY_COUNT):
        pair = (index * 74) % INTIMACY_COUNT
        lens_key, prompt, summary = INTIMACY_LENSES[pair // len(CONTEXTS)]
        context_key, context, context_tag = CONTEXTS[pair % len(CONTEXTS)]
        candidate = CandidateQuestion(
            client_id=f"r1-i-{index:03d}",
            kind=QuestionKind.FREE_TEXT,
            prompt=prompt.format(context=context),
            category=Category.INTIMACY,
            intimacy=True,
            concept_family=f"i-{context_key}-{lens_key}",
            concept_summary=f"{summary} in the context of {context}",
            theme_tags=[context_tag, "consent", lens_key],
        )
        entries.append(
            ReserveEntry(candidate, "intimacy-reviewed", normalized_hash(candidate.prompt))
        )
    return entries
