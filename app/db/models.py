import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint, Index, JSON
)
from sqlalchemy.orm import relationship
from app.db.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Rule(Base):
    __tablename__ = "rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    keyword = Column(String(255), nullable=False, index=True)
    dm_message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    executions = relationship("UserRuleExecution", back_populates="rule")
    jobs = relationship("DMJob", back_populates="rule")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class UserRuleExecution(Base):
    __tablename__ = "user_rule_executions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(255), nullable=False, index=True)
    rule_id = Column(String(36), ForeignKey("rules.id"), nullable=False)
    comment_id = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="DISPATCHED")  # BLOCKED_DUPLICATE, DISPATCHED, CANCELLED_DELETED
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    rule = relationship("Rule", back_populates="executions")

    __table_args__ = (
        UniqueConstraint("user_id", "rule_id", name="uq_user_rule"),
    )


class DMJob(Base):
    __tablename__ = "dm_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(255), nullable=False, index=True)
    rule_id = Column(String(36), ForeignKey("rules.id"), nullable=False)
    comment_id = Column(String(255), nullable=False, index=True)
    dm_message = Column(Text, nullable=False)
    pseudogram_dm_id = Column(String(255), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="QUEUED", index=True)  # QUEUED, SENT, FAILED, CANCELLED
    attempts = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    rule = relationship("Rule", back_populates="jobs")


class DuplicateLog(Base):
    __tablename__ = "duplicate_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    reason = Column(String(100), nullable=False)  # EVENT_DUPLICATE, USER_RULE_DUPLICATE
    event_id = Column(String(255), nullable=True)
    user_id = Column(String(255), nullable=True)
    rule_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
