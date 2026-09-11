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


class AdminMfa(Base):
    """Encrypted administrator TOTP enrollment and hashed recovery state."""

    __tablename__ = "admin_mfa"

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)
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
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    publish_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    intimacy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
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


class Note(Timestamped, Base):
    """Shared plain-text note with a monotonic server revision."""

    __tablename__ = "notes"
    __table_args__ = (CheckConstraint("revision >= 0"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    creation_operation_id: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


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
    __table_args__ = (UniqueConstraint("account_id", "sample_id"),)

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
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), index=True
    )
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    estimated_distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    corrected_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    correction_reason: Mapped[str | None] = mapped_column(String(240))
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Countdown(Timestamped, Base):
    """Shared countdown with an optimistic revision."""

    __tablename__ = "countdowns"
    __table_args__ = (CheckConstraint("revision >= 0"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    occurs_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CountdownOperation(Base):
    """Idempotency record for an offline countdown mutation."""

    __tablename__ = "countdown_operations"
    __table_args__ = (UniqueConstraint("couple_id", "operation_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    couple_id: Mapped[UUID] = mapped_column(ForeignKey("couples.id", ondelete="CASCADE"))
    operation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    countdown_id: Mapped[UUID] = mapped_column(
        ForeignKey("countdowns.id", ondelete="CASCADE")
    )
    resulting_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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
    selected_question_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(120))
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
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )


class ApkRelease(Timestamped, Base):
    """Published signed APK metadata while GitHub remains the file host."""

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
