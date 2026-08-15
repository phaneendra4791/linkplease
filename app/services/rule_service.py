from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Rule
from app.schemas.rules import RuleCreate, RuleResponse

async def create_rule(session: AsyncSession, rule_in: RuleCreate) -> RuleResponse:
    rule = Rule(
        keyword=rule_in.keyword,
        dm_message=rule_in.dm_message
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return RuleResponse(
        rule_id=rule.id,
        keyword=rule.keyword,
        dm_message=rule.dm_message
    )

async def get_all_rules(session: AsyncSession) -> list[Rule]:
    result = await session.execute(select(Rule))
    return list(result.scalars().all())
