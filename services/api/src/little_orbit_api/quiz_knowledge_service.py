"""Synchronize and retrieve only the reviewed quiz-writing Markdown corpus."""

from dataclasses import dataclass

from little_orbit_ai.embeddings import OllamaEmbeddingClient
from little_orbit_ai.knowledge import (
    KnowledgeChunk,
    corpus_revision,
    lexical_context,
    load_knowledge_chunks,
)
from little_orbit_ai.ollama import OllamaFailure
from sqlalchemy import select, update

from .clock import SystemClock
from .database import SessionFactory
from .quiz_intelligence_models import AiKnowledgeChunk


@dataclass(frozen=True)
class KnowledgeContext:
    """Bounded prompt snippets and the exact reviewed corpus revision."""

    snippets: list[str]
    revision: str
    semantic: bool


async def sync_reviewed_knowledge(client: OllamaEmbeddingClient) -> str:
    """Embed a changed corpus before atomically replacing its active revision."""

    chunks = load_knowledge_chunks()
    revision = corpus_revision(chunks)
    async with SessionFactory() as session:
        active_revisions = set(
            await session.scalars(
                select(AiKnowledgeChunk.revision_digest).where(AiKnowledgeChunk.active.is_(True))
            )
        )
    required = {item.revision_digest for item in chunks}
    if required and required.issubset(active_revisions):
        return revision
    vectors = await _embed_chunks(client, chunks)
    now = SystemClock().now()
    async with SessionFactory() as session:
        await session.execute(update(AiKnowledgeChunk).values(active=False))
        for item, vector in zip(chunks, vectors, strict=True):
            existing = await session.scalar(
                select(AiKnowledgeChunk).where(
                    AiKnowledgeChunk.document_key == item.document_key,
                    AiKnowledgeChunk.revision_digest == item.revision_digest,
                    AiKnowledgeChunk.chunk_index == item.index,
                )
            )
            record = existing or AiKnowledgeChunk(
                document_key=item.document_key,
                document_path=item.document_path,
                revision_digest=item.revision_digest,
                chunk_index=item.index,
                body=item.body,
                created_at=now,
            )
            record.embedding = vector
            record.embedding_model = client.settings.model
            record.embedding_digest = client.settings.manifest_digest
            record.active = True
            if existing is None:
                session.add(record)
        await session.commit()
    return revision


async def retrieve_knowledge(
    query: str, client: OllamaEmbeddingClient, limit: int = 6
) -> KnowledgeContext:
    """Retrieve nearest reviewed chunks, with a deterministic local-only fallback."""

    chunks = load_knowledge_chunks()
    revision = corpus_revision(chunks)
    try:
        vector = (await client.embed([query[:512]]))[0]
        async with SessionFactory() as session:
            records = list(
                await session.scalars(
                    select(AiKnowledgeChunk)
                    .where(
                        AiKnowledgeChunk.active.is_(True),
                        AiKnowledgeChunk.embedding_model == client.settings.model,
                        AiKnowledgeChunk.embedding_digest == client.settings.manifest_digest,
                    )
                    .order_by(AiKnowledgeChunk.embedding.cosine_distance(vector))
                    .limit(limit)
                )
            )
        if records:
            return KnowledgeContext([item.body for item in records], revision, True)
    except OllamaFailure:
        pass
    return KnowledgeContext(lexical_context(query, chunks, limit), revision, False)


async def _embed_chunks(
    client: OllamaEmbeddingClient, chunks: list[KnowledgeChunk]
) -> list[list[float]]:
    """Respect the embedding service's fixed batch bound."""

    vectors: list[list[float]] = []
    for start in range(0, len(chunks), 32):
        vectors.extend(await client.embed([item.body for item in chunks[start : start + 32]]))
    return vectors
