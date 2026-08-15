from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_db
from app.schemas.rules import RuleCreate, RuleResponse
from app.services.rule_service import create_rule

router = APIRouter(tags=["Rules"])

@router.post("/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_new_rule(rule_in: RuleCreate, db: AsyncSession = Depends(get_async_db)):
    return await create_rule(db, rule_in)
