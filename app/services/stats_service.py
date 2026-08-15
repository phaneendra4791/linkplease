from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.models import DMJob, DuplicateLog
from app.schemas.stats import StatsResponse

async def get_stats(session: AsyncSession) -> StatsResponse:
    # Sent count
    sent_res = await session.execute(
        select(func.count()).select_from(DMJob).where(DMJob.status == "SENT")
    )
    sent_count = sent_res.scalar() or 0

    # Failed count
    failed_res = await session.execute(
        select(func.count()).select_from(DMJob).where(DMJob.status == "FAILED")
    )
    failed_count = failed_res.scalar() or 0

    # Queued count
    queued_res = await session.execute(
        select(func.count()).select_from(DMJob).where(DMJob.status == "QUEUED")
    )
    queued_count = queued_res.scalar() or 0

    # Duplicates blocked count (duplicate events + duplicate user-rule attempts)
    dup_res = await session.execute(
        select(func.count()).select_from(DuplicateLog)
    )
    duplicates_blocked_count = dup_res.scalar() or 0

    return StatsResponse(
        sent=sent_count,
        failed=failed_count,
        queued=queued_count,
        duplicates_blocked=duplicates_blocked_count
    )
