"""Versioned request and response models for the public API."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AnyHttpUrl,
    EmailStr,
    Field,
    model_validator,
)

from .quiz_v2_schemas import (
    CustomQuestionV2Request as CustomQuestionV2Request,
)
from .quiz_v2_schemas import (
    CustomQuestionV2Response as CustomQuestionV2Response,
)
from .quiz_v2_schemas import (
    CustomQueueResponse as CustomQueueResponse,
)
from .quiz_v2_schemas import (
    FreeTextAnswer as FreeTextAnswer,
)
from .quiz_v2_schemas import (
    LegacyWeightedAnswer as LegacyWeightedAnswer,
)
from .quiz_v2_schemas import (
    MultipleChoiceAnswer as MultipleChoiceAnswer,
)
from .quiz_v2_schemas import (
    PartnerGuessAnswer as PartnerGuessAnswer,
)
from .quiz_v2_schemas import (
    QuestionReportV2Request as QuestionReportV2Request,
)
from .quiz_v2_schemas import (
    QuizAnswerV2 as QuizAnswerV2,
)
from .quiz_v2_schemas import (
    QuizDayMutation as QuizDayMutation,
)
from .quiz_v2_schemas import (
    QuizDayResponse as QuizDayResponse,
)
from .quiz_v2_schemas import (
    QuizDraftMutation as QuizDraftMutation,
)
from .quiz_v2_schemas import (
    QuizHistoryItem as QuizHistoryItem,
)
from .quiz_v2_schemas import (
    QuizOptionV2 as QuizOptionV2,
)
from .quiz_v2_schemas import (
    QuizQuestionV2 as QuizQuestionV2,
)
from .quiz_v2_schemas import (
    QuizStatusResponse as QuizStatusResponse,
)
from .quiz_v2_schemas import (
    SingleChoiceAnswer as SingleChoiceAnswer,
)
from .quiz_v2_schemas import (
    WeightedChoiceAnswer as WeightedChoiceAnswer,
)
from .schema_base import StrictModel, StrictText


class PublicMessage(StrictModel):
    """Enumeration-neutral response."""

    message: str


class RegistrationRequest(StrictModel):
    """Adult account registration payload."""

    email: EmailStr
    password: Annotated[str, Field(min_length=12, max_length=256)]
    display_name: Annotated[StrictText, Field(min_length=1, max_length=80)]
    is_adult: Literal[True]
    accepted_terms_version: Literal["2026-09-10"]
    website: str = Field(default="", max_length=200, description="Invisible honeypot")


class LoginRequest(StrictModel):
    """Email/password login payload."""

    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=256)]


class ForgotPasswordRequest(StrictModel):
    """Email-only recovery request with a neutral public response."""

    email: EmailStr


class ResetPasswordRequest(StrictModel):
    """One-use password reset proof and replacement password."""

    token: Annotated[str, Field(min_length=32, max_length=256)]
    password: Annotated[str, Field(min_length=12, max_length=256)]


class SessionResponse(StrictModel):
    """Opaque session returned only after successful authentication."""

    access_token: str
    expires_at: datetime
    account_id: UUID


class TokenRequest(StrictModel):
    """One-use verification or recovery token."""

    token: Annotated[str, Field(min_length=32, max_length=256)]


class PairCodeResponse(StrictModel):
    """Pair code shown only to its creator."""

    code: str
    expires_at: datetime


class PairRedeemRequest(StrictModel):
    """Pair code entered by the invited partner."""

    code: Annotated[str, Field(pattern=r"^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$")]


class PairPendingResponse(StrictModel):
    """Pending request metadata that avoids exposing an email address."""

    request_id: UUID
    partner_display_name: str
    expires_at: datetime


class PairConfirmRequest(StrictModel):
    """Creator confirmation for the pending partner."""

    request_id: UUID


class PairingState(StrictModel):
    """Current result of a create-confirm pairing transition."""

    state: Literal["awaiting_creator_confirmation", "paired"]
    request_id: UUID
    couple_id: UUID | None


class CouplePreferencesRequest(StrictModel):
    """One member's consent plus shared estimate settings."""

    intimacy_enabled: bool | None = None
    location_enabled: bool | None = None
    proximity_threshold_m: float | None = Field(default=None, ge=25, le=1000)
    home_timezone: Annotated[StrictText, Field(min_length=1, max_length=64)] | None = None


class CouplePreferencesResponse(StrictModel):
    """Current member choices and whether both partners consent."""

    couple_id: UUID
    anniversary_date: date | None
    proximity_threshold_m: float
    intimacy_enabled_by_me: bool
    intimacy_enabled_by_both: bool
    location_enabled_by_me: bool
    location_enabled_by_both: bool
    home_timezone: str


class UnpairResponse(StrictModel):
    """Former relationship reference retained as a private archive."""

    archive_id: UUID
    ended_at: datetime


class ArchiveSummary(StrictModel):
    """Private read-only former-pairing summary."""

    archive_id: UUID
    partner_display_name: str
    joined_at: datetime
    ended_at: datetime


class ArchiveDetail(ArchiveSummary):
    """Former-pairing content visible only to the original member."""

    notes: list[dict[str, object]]
    countdowns: list[dict[str, object]]
    quiz_answers: list[dict[str, object]]
    smooches: list[dict[str, object]]


class CustomQuestionRequest(StrictModel):
    """Couple-authored question with the same interaction rules as global content."""

    publish_date: date
    kind: Literal[
        "single_choice",
        "multiple_choice",
        "free_text",
        "partner_guess",
        "weighted_scale",
    ]
    prompt: Annotated[StrictText, Field(min_length=12, max_length=240)]
    category: Literal["everyday", "memories", "dreams", "values", "playful", "connection", "intimacy"]
    intimacy: bool
    options: list[Annotated[StrictText, Field(min_length=1, max_length=80)]] = Field(
        max_length=8
    )

    @model_validator(mode="after")
    def validate_shape(self) -> "CustomQuestionRequest":
        """Keep kind, options, and explicit intimacy tagging consistent."""

        choice = {"single_choice", "multiple_choice", "partner_guess"}
        if self.kind in choice and not 2 <= len(self.options) <= 8:
            raise ValueError("choice questions require 2-8 options")
        if self.kind not in choice and self.options:
            raise ValueError("free text and weighted scale questions have no options")
        if len(set(self.options)) != len(self.options):
            raise ValueError("options must be unique")
        if self.intimacy != (self.category == "intimacy"):
            raise ValueError("intimacy flag must match the intimacy category")
        return self


class QuestionReportRequest(StrictModel):
    """Reason for immediately hiding a question from one couple."""

    reason: Annotated[StrictText, Field(min_length=3, max_length=500)]


class QuestionResponse(StrictModel):
    """Daily question without either partner's hidden answer."""

    id: UUID
    publish_date: date
    kind: str
    prompt: str
    category: str
    options: list[str]
    submitted_by_me: bool
    both_submitted: bool
    my_answer: dict[str, object] | None = None
    partner_answer: dict[str, object] | None = None


class QuizAnswerRequest(StrictModel):
    """Validated answer envelope; type-specific checks run in the domain service."""

    answer: dict[str, object]


class CountdownMutation(StrictModel):
    """Retry-safe shared countdown mutation."""

    operation_id: UUID
    title: Annotated[StrictText, Field(min_length=1, max_length=120)]
    occurs_at: datetime
    timezone: Annotated[StrictText, Field(min_length=1, max_length=64)]
    notes: Annotated[StrictText, Field(max_length=1000)] = ""
    expected_revision: int | None = Field(default=None, ge=0)


class CountdownResponse(StrictModel):
    """Shared countdown state returned to either active partner."""

    id: UUID
    title: str
    occurs_at: datetime
    timezone: str
    notes: str
    revision: int
    updated_at: datetime


class CountdownDeleteRequest(StrictModel):
    """Retry-safe optimistic countdown deletion."""

    operation_id: UUID
    expected_revision: int = Field(ge=0)


class LocationSampleRequest(StrictModel):
    """One consented, short-lived coordinate sample."""

    sample_id: UUID
    recorded_at: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(gt=0, le=1000)


class LocationBatchRequest(StrictModel):
    """Bounded offline upload whose sample IDs make retries harmless."""

    samples: list[LocationSampleRequest] = Field(min_length=1, max_length=48)


class LocationBatchResponse(StrictModel):
    """Location ingestion result without echoing coordinates."""

    accepted: int
    duplicates: int
    together_minutes_added: int


class TogetherSummary(StrictModel):
    """Estimated together-time and its recency."""

    estimated_seconds: int
    last_updated_at: datetime | None
    proximity_threshold_m: float
    label: Literal["estimate"]


class TogetherBucketResponse(StrictModel):
    """One non-overlapping estimated minute without either coordinate."""

    id: UUID
    bucket_start: datetime
    duration_seconds: int
    corrected_at: datetime | None


class TogetherCorrectionRequest(StrictModel):
    """Audited correction to one non-overlapping minute bucket."""

    duration_seconds: int = Field(ge=0, le=60)
    reason: Annotated[StrictText, Field(min_length=3, max_length=240)]


class RelationshipStartProposalRequest(StrictModel):
    """Retry-safe proposal for the couple's shared relationship start date."""

    operation_id: UUID
    proposed_date: date


class RelationshipStartDecisionRequest(StrictModel):
    """Retry-safe decision whose allowed actions depend on the current actor."""

    operation_id: UUID
    decision: Literal["accept", "decline", "cancel"]


class RelationshipStartProposalResponse(StrictModel):
    """Content-safe pending or completed relationship-date proposal state."""

    id: UUID
    proposed_date: date
    proposed_by_me: bool
    status: Literal["pending", "accepted", "declined", "cancelled", "expired"]
    expires_at: datetime


class TogetherSummaryV2(StrictModel):
    """Relationship age and separate location-derived nearby estimate."""

    relationship_start_date: date | None
    relationship_days: int | None
    nearby_estimated_seconds: int
    nearby_last_processed_at: datetime | None
    proximity_threshold_m: float
    location_enabled_by_me: bool
    location_enabled_by_both: bool
    label: Literal["estimate"]
    pending_start_date: RelationshipStartProposalResponse | None


class TogetherSummaryV3(StrictModel):
    """Pair-age clock plus a separate, explicitly estimated nearby total."""

    paired_at: datetime
    paired_days: int
    nearby_estimated_seconds: int
    nearby_last_processed_at: datetime | None
    proximity_threshold_m: float
    location_enabled_by_me: bool
    location_enabled_by_both: bool
    label: Literal["estimate"]


class TogetherHistoryDay(StrictModel):
    """One UTC day of coordinate-free nearby history."""

    day: date
    estimated_seconds: int
    corrected: bool


class LocationBatchV2Response(StrictModel):
    """Location ingestion result for deterministic interval recomputation."""

    accepted: int
    duplicates: int
    nearby_seconds_recomputed: int


class AccountExportResponse(StrictModel):
    """Portable account and relationship data prepared for its owner."""

    generated_at: datetime
    data: dict[str, object]


class AccountDeletionRequest(StrictModel):
    """Recent password proof for scheduling full account erasure."""

    password: Annotated[str, Field(min_length=1, max_length=256)]


class AccountDeletionResponse(StrictModel):
    """Deletion schedule after sessions and sharing are revoked."""

    job_id: UUID
    execute_after: datetime


class HealthResponse(StrictModel):
    """Health status suitable for a load balancer or public status page."""

    status: Literal["ok", "degraded"]
    service: str
    version: str
    checked_at: datetime


class AdminConfigResponse(StrictModel):
    """Configuration dictionary whose secret values are already redacted."""

    values: dict[str, object]


class AdminCollectionResponse(StrictModel):
    """Bounded privacy-safe owner-console rows."""

    items: list[dict[str, object]]


class AdminOverviewResponse(StrictModel):
    """Operational-safe operational counters and service state."""

    values: dict[str, object]


class AdminAccountAction(StrictModel):
    """Suspend or restore one account."""

    suspended: bool


class AdminQuestionAction(StrictModel):
    """Resolve a report and optionally disable a global question."""

    disable_question: bool = False


class AdminRegistrationControl(StrictModel):
    """Pause or resume public registration without changing secrets."""

    enabled: bool


class CuratedQuestionInput(StrictModel):
    """Owner-reviewed fallback question definition."""

    stable_key: Annotated[str, Field(pattern=r"^[a-z0-9-]{3,48}$")]
    kind: Literal[
        "single_choice",
        "multiple_choice",
        "free_text",
        "partner_guess",
        "weighted_choice",
    ]
    prompt: Annotated[StrictText, Field(min_length=12, max_length=240)]
    category: Literal[
        "everyday", "memories", "dreams", "values", "playful", "connection", "intimacy"
    ]
    intimacy: bool
    options: list[Annotated[StrictText, Field(min_length=1, max_length=64)]] = Field(
        max_length=6
    )
    option_icons: list[
        Literal[
            "heart", "chat", "home", "meal", "movie", "music", "outdoors", "play",
            "rest", "star", "travel", "surprise"
        ]
    ] = Field(max_length=6)
    scale_low_label: Annotated[StrictText, Field(min_length=1, max_length=32)] | None = None
    scale_high_label: Annotated[StrictText, Field(min_length=1, max_length=32)] | None = None
    enabled: bool = True


class CuratedImportRequest(StrictModel):
    """Atomic replacement set for the editable curated bank."""

    questions: list[CuratedQuestionInput] = Field(min_length=6, max_length=500)


class ApkReleaseInput(StrictModel):
    """Signed APK metadata for first-party publication or a legacy GitHub release."""

    version: Annotated[
        StrictText,
        Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$", max_length=40),
    ]
    version_code: int = Field(gt=0)
    apk_url: AnyHttpUrl
    github_release_url: AnyHttpUrl
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    size_bytes: int = Field(gt=0, le=2_147_483_648)
    package_name: Literal["com.littleorbit.mobile"]
    signer_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    wear_apk_url: AnyHttpUrl | None = None
    wear_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None = None
    wear_size_bytes: int | None = Field(default=None, gt=0, le=2_147_483_648)
    wear_package_name: Literal["com.littleorbit.mobile"] | None = None
    wear_version_code: int | None = Field(default=None, gt=0)
    wear_minimum_android: int | None = Field(default=None, ge=30, le=36)
    minimum_android: int = Field(ge=29, le=36)
    minimum_supported_version_code: int = Field(ge=1)
    required_after: datetime | None = None
    release_notes: Annotated[StrictText, Field(min_length=1, max_length=4000)]
    publish: bool = False

    @model_validator(mode="after")
    def validate_release_authority(self) -> "ApkReleaseInput":
        """Restrict releases to the canonical repository and monotonic compatibility floor."""

        expected_tag = f"v{self.version}"
        _validate_apk_release_url(self.apk_url, expected_tag)
        _validate_wear_release(self, expected_tag)
        _validate_github_release_url(self.github_release_url, expected_tag)
        _validate_version_floor(self.minimum_supported_version_code, self.version_code)
        _validate_required_after(self.required_after)
        return self


def _validate_wear_release(release: ApkReleaseInput, expected_tag: str) -> None:
    """Require one complete first-party Wear tuple for published RC6+ metadata."""

    fields = (
        release.wear_apk_url,
        release.wear_sha256,
        release.wear_size_bytes,
        release.wear_package_name,
        release.wear_version_code,
        release.wear_minimum_android,
    )
    if not any(value is not None for value in fields):
        if release.publish and release.version_code >= 6:
            raise ValueError("RC6 and later releases require complete Wear metadata")
        return
    if not all(value is not None for value in fields):
        raise ValueError("Wear release metadata must be complete")
    from .release_artifacts import is_hosted_wear_apk_url

    version = expected_tag.removeprefix("v")
    if not is_hosted_wear_apk_url(str(release.wear_apk_url), version):
        raise ValueError("Wear APK URL must use the matching Little Orbit API endpoint")


def _canonical_github_url(url: AnyHttpUrl) -> bool:
    """Accept only query-free HTTPS URLs on the canonical release authority."""

    return (url.scheme, url.host, url.port, url.username, url.password, url.query, url.fragment) == (
        "https",
        "github.com",
        443,
        None,
        None,
        None,
        None,
    )


def _validate_apk_release_url(url: AnyHttpUrl, expected_tag: str) -> None:
    """Require the matching first-party endpoint or legacy canonical GitHub asset."""

    from .release_artifacts import is_hosted_apk_url

    version = expected_tag.removeprefix("v")
    if is_hosted_apk_url(str(url), version):
        return
    path = url.path or ""
    prefix = f"/Captainpax/littleorbit/releases/download/{expected_tag}/"
    if not _canonical_github_url(url) or not (path.startswith(prefix) and path.endswith(".apk")):
        raise ValueError("APK URL must use the Little Orbit API or canonical GitHub release")


def _validate_github_release_url(url: AnyHttpUrl, expected_tag: str) -> None:
    """Require the human-facing page for the same immutable release tag."""

    expected_path = f"/Captainpax/littleorbit/releases/tag/{expected_tag}"
    if not _canonical_github_url(url) or url.path != expected_path:
        raise ValueError("release URL must match the canonical Little Orbit tag")


def _validate_version_floor(floor: int, release_version: int) -> None:
    """Prevent a release from requiring a version newer than itself."""

    if floor > release_version:
        raise ValueError("minimum supported version cannot exceed the release version")


def _validate_required_after(value: datetime | None) -> None:
    """Reject ambiguous local timestamps at the compatibility boundary."""

    if value is not None and value.utcoffset() is None:
        raise ValueError("required-after timestamp must include a timezone")


class ApkReleaseResponse(StrictModel):
    """Latest public signed APK metadata."""

    version: str
    version_code: int
    apk_url: str
    github_release_url: str
    sha256: str
    size_bytes: int
    package_name: str
    signer_sha256: str
    wear_apk_url: str | None
    wear_sha256: str | None
    wear_size_bytes: int | None
    wear_package_name: str | None
    wear_version_code: int | None
    wear_minimum_android: int | None
    minimum_android: int
    minimum_supported_version_code: int
    required_after: datetime | None
    release_notes: str
    published_at: datetime


class ClientUpdateRequired(StrictModel):
    """Stable compatibility response that contains no account or relationship state."""

    code: Literal["client_update_required"] = "client_update_required"
    minimum_version_code: int
    release_url: Literal["/v1/releases/current"] = "/v1/releases/current"


class AdminEnrollmentStart(StrictModel):
    """Recent password proof required before revealing an enrollment URI."""

    password: Annotated[str, Field(min_length=1, max_length=256)]


class AdminEnrollmentChallenge(StrictModel):
    """Temporary authenticator enrollment material."""

    otpauth_uri: str
    qr_svg_data_url: str


class AdminEnrollmentConfirm(StrictModel):
    """First authenticator code that proves enrollment succeeded."""

    code: Annotated[str, Field(pattern=r"^[0-9]{6}$")]


class AdminSessionRequest(StrictModel):
    """Password plus TOTP or a one-time recovery code."""

    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=256)]
    totp_code: Annotated[str | None, Field(default=None, pattern=r"^[0-9]{6}$")]
    recovery_code: Annotated[str | None, Field(default=None, min_length=13, max_length=32)]


class AdminSessionResponse(SessionResponse):
    """MFA-verified owner session and recovery codes shown during enrollment only."""

    recovery_codes: list[str] = Field(default_factory=list)
