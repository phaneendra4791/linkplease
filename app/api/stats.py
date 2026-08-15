from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_db
from app.schemas.stats import StatsResponse
from app.services.stats_service import get_stats

router = APIRouter(tags=["Stats"])

@router.get("/stats", response_model=StatsResponse)
async def fetch_stats(db: AsyncSession = Depends(get_async_db)):
    return await get_stats(db)
