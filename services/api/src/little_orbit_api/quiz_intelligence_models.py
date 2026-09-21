"""Persistence for private quiz feedback and global semantic intelligence."""

from datetime import date, datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class QuizFeedbackRollout(Base):
    """Server-recorded launch instant so older reveals never become rateable."""

    __tablename__ = "quiz_feedback_rollout"

    feature: Mapped[str] = mapped_column(String(40), primary_key=True)
    enabled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QuestionConcept(Base):
    """Canonical concept identity and versioned local embeddings for one global question."""

    __tablename__ = "question_concepts"
    __table_args__ = (
        Index("ix_question_concepts_family", "concept_family"),
        Index("ix_question_concepts_model", "embedding_model", "embedding_digest"),
    )

    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    concept_family: Mapped[str] = mapped_column(String(80), nullable=False)
    concept_summary: Mapped[str] = mapped_column(String(180), nullable=False)
    prompt_embedding: Mapped[list[float] | None] = mapped_column(Vector(768))
    concept_embedding: Mapped[list[float] | None] = mapped_column(Vector(768))
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding_digest: Mapped[str] = mapped_column(String(80), nullable=False)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QuestionFeedback(Base):
    """Attributable, editable feedback retained for at most thirty days."""

    __tablename__ = "question_feedback"
    __table_args__ = (
        UniqueConstraint(
            "quiz_day_id", "question_id", "account_id", name="uq_question_feedback_actor"
        ),
        CheckConstraint("stars BETWEEN 1 AND 5", name="ck_question_feedback_stars"),
        CheckConstraint("revision >= 1", name="ck_question_feedback_revision"),
        Index("ix_question_feedback_expiry", "editable_until"),
        Index("ix_question_feedback_question", "question_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    quiz_day_id: Mapped[UUID] = mapped_column(
        ForeignKey("quiz_days.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    couple_id: Mapped[UUID] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    stars: Mapped[int] = mapped_column(Integer, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sanitized_review: Mapped[str | None] = mapped_column(String(300))
    review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    editable_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class QuestionFeedbackOperation(Base):
    """Retry record for feedback create, edit, and delete operations."""

    __tablename__ = "question_feedback_operations"
    __table_args__ = (
        UniqueConstraint("account_id", "operation_id", name="uq_feedback_operation_actor"),
        Index("ix_feedback_operations_expiry", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    operation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    feedback_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("question_feedback.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    result_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    result_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AnonymousQuestionReview(Base):
    """Unlinked feedback retained only long enough for bounded review analysis."""

    __tablename__ = "anonymous_question_reviews"
    __table_args__ = (
        Index("ix_anonymous_reviews_question_week", "question_id", "week_start"),
        Index("ix_anonymous_reviews_expiry", "expires_at"),
        CheckConstraint("stars BETWEEN 1 AND 5", name="ck_anonymous_review_stars"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    stars: Mapped[int] = mapped_column(Integer, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sanitized_review: Mapped[str | None] = mapped_column(String(300))
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FeedbackWeeklyAggregate(Base):
    """Identity-free weekly learning input that may outlive raw feedback."""

    __tablename__ = "feedback_weekly_aggregates"
    __table_args__ = (
        UniqueConstraint("question_id", "week_start", name="uq_feedback_aggregate_week"),
        CheckConstraint("rating_count >= 0", name="ck_feedback_aggregate_count"),
        CheckConstraint("distinct_accounts >= 0", name="ck_feedback_aggregate_accounts"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False)
    distinct_accounts: Mapped[int] = mapped_column(Integer, nullable=False)
    score_sum: Mapped[int] = mapped_column(Integer, nullable=False)
    tag_counts: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    themes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AiPolicyVersion(Base):
    """Bounded learned generation policy with transactional activation."""

    __tablename__ = "ai_policy_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('staged', 'active', 'rejected', 'superseded', 'rolled_back')",
            name="ck_ai_policy_status",
        ),
        Index(
            "uq_ai_policy_one_active",
            "status",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    version: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    policy_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    evaluation_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AiRun(Base):
    """Content-free provenance for learning, generation, and repair runs."""

    __tablename__ = "ai_runs"
    __table_args__ = (
        UniqueConstraint("run_key", name="uq_ai_runs_key"),
        CheckConstraint(
            "status IN ('running', 'passed', 'failed', 'fallback', 'cancelled')",
            name="ck_ai_run_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_key: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    policy_version: Mapped[int | None] = mapped_column(Integer)
    summary_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QuestionReserve(Base):
    """Versioned, unassigned question used only for atomic safe fallback."""

    __tablename__ = "question_reserve"
    __table_args__ = (
        UniqueConstraint("stable_key", name="uq_question_reserve_key"),
        Index("ix_question_reserve_available", "intimacy", "consumed_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    stable_key: Mapped[str] = mapped_column(String(80), nullable=False)
    bank_version: Mapped[int] = mapped_column(Integer, nullable=False)
    concept_family: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    intimacy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    option_icons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    scale_low_label: Mapped[str | None] = mapped_column(String(32))
    scale_high_label: Mapped[str | None] = mapped_column(String(32))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WebContextSource(Base):
    """Audited HTTPS origin allowed to contribute public non-user context."""

    __tablename__ = "web_context_sources"
    __table_args__ = (UniqueConstraint("base_url", name="uq_web_context_source_url"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    hostname: Mapped[str] = mapped_column(String(253), nullable=False)
    code_owned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    added_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
