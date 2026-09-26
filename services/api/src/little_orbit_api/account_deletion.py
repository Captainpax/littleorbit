"""Terminal account-erasure transaction helpers."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .attachment_models import NoteAttachment
from .models import Account, Couple, CoupleMember, DeletionJob, MailOutbox


async def complete_deletion_job(
    session: AsyncSession, job: DeletionJob, completed_at: datetime
) -> list[str]:
    """Erase the account and every relationship container it participated in.

    Returning attachment keys lets the worker remove private bytes only after the
    database transaction commits. Erasing the couple also invalidates the former
    partner's relationship state and cascades all shared content.
    """

    account_id = job.account_id
    job.status = "completed"
    job.completed_at = completed_at
    job.account_id = None
    if account_id is None:
        return []
    account = await session.get(Account, account_id, with_for_update=True)
    if account is None:
        return []
    couple_ids = list(
        dict.fromkeys(
            await session.scalars(
                select(CoupleMember.couple_id).where(CoupleMember.account_id == account.id)
            )
        )
    )
    attachment_keys: list[str] = []
    if couple_ids:
        attachment_keys = list(
            await session.scalars(
                select(NoteAttachment.storage_key).where(
                    NoteAttachment.couple_id.in_(couple_ids)
                )
            )
        )
        await session.execute(delete(Couple).where(Couple.id.in_(couple_ids)))
    await session.execute(delete(MailOutbox).where(MailOutbox.recipient == account.email_normalized))
    await session.delete(account)
    return attachment_keys
