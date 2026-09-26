"""Persistence models and database-enforced Little Orbit invariants."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Timestamped:
    """Common server timestamps stored as timezone-aware UTC instants."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Account(Timestamped, Base):
    """A verified or pending adult account."""

    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email_normalized: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_adult: Mapped[bool] = mapped_column(Boolean, nullable=False)
    accepted_terms_version: Mapped[str] = mapped_column(String(24), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class OneUseToken(Base):
    """Hashed verification or password-reset token."""

    __tablename__ = "one_use_tokens"
    __table_args__ = (Index("ix_one_use_token_hash", "token_hash", unique=True),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Session(Base):
    """Opaque revocable account session stored as a token hash."""

    __tablename__ = "sessions"
    __table_args__ = (Index("ix_session_token_hash", "token_hash", unique=True),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    admin_mfa_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RateLimitBucket(Base):
    """Bounded fixed-window counter keyed only by a hashed subject."""

    __tablename__ = "rate_limit_buckets"
    __table_args__ = (
        CheckConstraint("count >= 1", name="ck_rate_limit_bucket_positive"),
        Index("ix_rate_limit_buckets_expiry", "scope", "window_started_at"),
    )

    scope: Mapped[str] = mapped_column(String(48), primary_key=True)
    subject_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AdminMfa(Base):
    """Encrypted administrator TOTP enrollment and hashed recovery state."""

    __tablename__ = "admin_mfa"

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)
    pending_encrypted_secret: Mapped[str | None] = mapped_column(Text)
    pending_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_hashes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_accepted_counter: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Couple(Timestamped, Base):
    """Two-person relationship container."""

    __tablename__ = "couples"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    anniversary_date: Mapped[date | None] = mapped_column(Date)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proximity_threshold_m: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    proximity_processed_through: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    proximity_algorithm_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2
    )
    home_timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="America/Los_Angeles"
    )


class CoupleMember(Base):
    """Membership with one active couple per account."""

    __tablename__ = "couple_members"
    __table_args__ = (
        UniqueConstraint("couple_id", "account_id"),
        Index(
            "uq_active_couple_member_account",
            "account_id",
            unique=True,
            postgresql_where=sql_text("left_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(ForeignKey("couples.id", ondelete="CASCADE"))
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    intimacy_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    location_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PairCode(Base):
    """Single-use pair code and its pending redeemer."""

    __tablename__ = "pair_codes"
    __table_args__ = (Index("ix_pair_code_hash", "code_hash", unique=True),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    creator_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    pending_partner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Question(Base):
    """Validated global or couple-created question."""

    __tablename__ = "questions"
    __table_args__ = (
        Index(
            "uq_questions_scope_normalized_hash",
            "publish_date",
            "couple_id",
            "normalized_hash",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        Index(
            "uq_global_question_order",
            "publish_date",
            "display_order",
            unique=True,
            postgresql_where=sql_text(
                "couple_id IS NULL AND intimacy IS FALSE AND display_order IS NOT NULL"
            ),
        ),
        Index(
            "uq_custom_question_slot",
            "couple_id",
            "publish_date",
            "custom_slot",
            unique=True,
            postgresql_where=sql_text("couple_id IS NOT NULL AND custom_slot IS NOT NULL"),
        ),
        Index(
            "ix_questions_prompt_trgm",
            "prompt",
            postgresql_using="gin",
            postgresql_ops={"prompt": "gin_trgm_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    publish_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    intimacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    option_icons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    scale_low_label: Mapped[str | None] = mapped_column(String(32))
    scale_high_label: Mapped[str | None] = mapped_column(String(32))
    interaction_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    display_order: Mapped[int | None] = mapped_column(Integer)
    custom_slot: Mapped[int | None] = mapped_column(Integer)
    surprise: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    couple_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QuizAnswer(Base):
    """One person's hidden answer for one daily question."""

    __tablename__ = "quiz_answers"
    __table_args__ = (UniqueConstraint("question_id", "account_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id"))
    couple_id: Mapped[UUID] = mapped_column(ForeignKey("couples.id", ondelete="CASCADE"))
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    answer: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QuizDay(Base):
    """Stable five-question snapshot and atomic shared-reveal state."""

    __tablename__ = "quiz_days"
    __table_args__ = (
        UniqueConstraint("couple_id", "quiz_date"),
        CheckConstraint("revision >= 0"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), index=True
    )
    quiz_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QuizDayQuestion(Base):
    """Ordered question selected for one couple's immutable daily snapshot."""

    __tablename__ = "quiz_day_questions"
    __table_args__ = (
        UniqueConstraint("quiz_day_id", "position"),
        UniqueConstraint("quiz_day_id", "question_id"),
        CheckConstraint("position BETWEEN 1 AND 5"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    quiz_day_id: Mapped[UUID] = mapped_column(
        ForeignKey("quiz_days.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class QuizDayMember(Base):
    """One member's reversible finish marker before shared reveal."""

    __tablename__ = "quiz_day_members"
    __table_args__ = (UniqueConstraint("quiz_day_id", "account_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    quiz_day_id: Mapped[UUID] = mapped_column(
        ForeignKey("quiz_days.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QuizDraft(Base):
    """One revisioned private answer draft for a v2 daily question."""

    __tablename__ = "quiz_drafts"
    __table_args__ = (
        UniqueConstraint("quiz_day_id", "question_id", "account_id"),
        CheckConstraint("revision >= 1"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    quiz_day_id: Mapped[UUID] = mapped_column(
        ForeignKey("quiz_days.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    answer: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QuizOperation(Base):
    """Retry-safe quiz mutation result scoped to one authenticated member."""

    __tablename__ = "quiz_operations"
    __table_args__ = (UniqueConstraint("couple_id", "account_id", "operation_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), index=True
    )
    operation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    result: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Note(Timestamped, Base):
    """Shared plain-text note with a monotonic server revision."""

    __tablename__ = "notes"
    __table_args__ = (
        CheckConstraint("revision >= 0"),
        CheckConstraint("metadata_revision >= 0"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    creation_operation_id: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class NoteOperation(Base):
    """Retry-safe applied edit and resulting revision."""

    __tablename__ = "note_operations"
    __table_args__ = (UniqueConstraint("note_id", "operation_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    note_id: Mapped[UUID] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"))
    operation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    resulting_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    edit: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LocationSample(Base):
    """Short-lived raw coordinate used only for proximity calculation."""

    __tablename__ = "location_samples"
    __table_args__ = (
        UniqueConstraint("account_id", "sample_id"),
        Index(
            "ix_location_samples_couple_account_recorded",
            "couple_id",
            "account_id",
            "recorded_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    sample_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    couple_id: Mapped[UUID] = mapped_column(ForeignKey("couples.id", ondelete="CASCADE"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_m: Mapped[float] = mapped_column(Float, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class TogetherBucket(Base):
    """One non-overlapping minute of estimated together-time."""

    __tablename__ = "together_buckets"
    __table_args__ = (
        UniqueConstraint("couple_id", "bucket_start"),
        CheckConstraint("duration_seconds >= 0 AND duration_seconds <= 60"),
        CheckConstraint(
            "observed_seconds >= 0 AND observed_seconds <= 60 "
            "AND bridged_seconds >= 0 AND bridged_seconds <= 60 "
            "AND unverified_seconds >= 0 AND unverified_seconds <= 60 "
            "AND apart_seconds >= 0 AND apart_seconds <= 60 "
            "AND poor_accuracy_seconds >= 0 AND poor_accuracy_seconds <= 60"
        ),
        CheckConstraint("duration_seconds = observed_seconds + bridged_seconds"),
        CheckConstraint(
            "observed_seconds + bridged_seconds + unverified_seconds + "
            "apart_seconds + poor_accuracy_seconds <= 60"
        ),
        Index("ix_together_buckets_couple_start", "couple_id", "bucket_start"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), index=True
    )
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    estimated_distance_m: Mapped[float | None] = mapped_column(Float)
    evidence_kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="observed"
    )
    observed_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bridged_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unverified_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    apart_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    poor_accuracy_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    algorithm_version: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    corrected_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    correction_reason: Mapped[str | None] = mapped_column(String(240))
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QuestionReport(Base):
    """Couple-scoped immediate hide and owner review record."""

    __tablename__ = "question_reports"
    __table_args__ = (UniqueConstraint("question_id", "couple_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    couple_id: Mapped[UUID] = mapped_column(ForeignKey("couples.id", ondelete="CASCADE"))
    reporter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeletionJob(Base):
    """Scheduled account erasure with immediate access revocation."""

    __tablename__ = "deletion_jobs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), unique=True
    )
    execute_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="scheduled")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GenerationBatch(Base):
    """Privacy-safe provenance and validation result for one global AI pool."""

    __tablename__ = "generation_batches"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    publish_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    model_digest: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    parameters: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    validation_results: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    candidate_snapshot: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    selected_question_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(120))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    day_theme_id: Mapped[UUID | None] = mapped_column(ForeignKey("quiz_day_themes.id", ondelete="SET NULL"))
    knowledge_revision: Mapped[str | None] = mapped_column(String(64))
    context_digest: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CuratedBankQuestion(Timestamped, Base):
    """Owner-reviewed fallback question stored independently of couple content."""

    __tablename__ = "curated_bank_questions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    stable_key: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    intimacy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    option_icons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    scale_low_label: Mapped[str | None] = mapped_column(String(32))
    scale_high_label: Mapped[str | None] = mapped_column(String(32))
    concept_family: Mapped[str] = mapped_column(String(80), nullable=False, default="legacy")
    concept_summary: Mapped[str] = mapped_column(String(180), nullable=False, default="Legacy concept")
    depth: Mapped[str] = mapped_column(String(16), nullable=False, default="reflective")
    theme_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))


class ApkRelease(Timestamped, Base):
    """Published signed APK metadata for first-party delivery and GitHub mirroring."""

    __tablename__ = "apk_releases"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    version_code: Mapped[int | None] = mapped_column(Integer, unique=True)
    apk_url: Mapped[str] = mapped_column(Text, nullable=False)
    github_release_url: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    package_name: Mapped[str | None] = mapped_column(String(160))
    signer_sha256: Mapped[str | None] = mapped_column(String(64))
    wear_apk_url: Mapped[str | None] = mapped_column(Text)
    wear_sha256: Mapped[str | None] = mapped_column(String(64))
    wear_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    wear_package_name: Mapped[str | None] = mapped_column(String(160))
    wear_version_code: Mapped[int | None] = mapped_column(Integer)
    wear_minimum_android: Mapped[int | None] = mapped_column(Integer)
    minimum_android: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_supported_version_code: Mapped[int | None] = mapped_column(Integer)
    required_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_notes: Mapped[str] = mapped_column(String(4000), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )


class RuntimeSetting(Base):
    """Owner-controlled non-secret setting with an attributable update."""

    __tablename__ = "runtime_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )


class SecurityEvent(Base):
    """Privacy-safe audit event with structured metadata."""

    __tablename__ = "security_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    outcome: Mapped[str] = mapped_column(String(32))
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MailOutbox(Base):
    """Encrypted short-lived email payload awaiting provider-neutral SMTP delivery."""

    __tablename__ = "mail_outbox"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(160), nullable=False)
    encrypted_body: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
