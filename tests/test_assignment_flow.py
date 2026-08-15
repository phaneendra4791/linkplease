import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Rule, WebhookEvent, UserRuleExecution, DMJob, DuplicateLog
from app.workers.tasks import process_webhook_event_task, send_dm_task, reconcile_dm_status_task

# In-memory SQLite sync engine for testing worker tasks synchronously
TEST_SYNC_ENGINE = create_engine("sqlite:///:memory:", echo=False)
TestingSyncSessionLocal = sessionmaker(bind=TEST_SYNC_ENGINE, autocommit=False, autoflush=False)

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=TEST_SYNC_ENGINE)
    with patch("app.workers.tasks.SyncSessionLocal", TestingSyncSessionLocal):
        yield
    Base.metadata.drop_all(bind=TEST_SYNC_ENGINE)

def test_complete_comment_to_dm_flow():
    db = TestingSyncSessionLocal()

    # 1. Create Rule
    rule = Rule(id="rule_price_1", keyword="PRICE", dm_message="Here is the price list.")
    db.add(rule)
    db.commit()

    # 2. Receive Webhook Event
    event_payload = {
        "event_id": "evt_flow_01",
        "event_type": "comment.created",
        "sent_at": "2026-08-10T09:14:22.481Z",
        "data": {
            "comment_id": "cmt_flow_01",
            "post_id": "post_flow_1",
            "text": "Can I get the PRICE please?",
            "from": {
                "user_id": "usr_flow_user_1",
                "username": "user1"
            }
        }
    }
    event = WebhookEvent(
        event_id="evt_flow_01",
        event_type="comment.created",
        payload=event_payload,
        processed=False
    )
    db.add(event)
    db.commit()

    # 3. Execute process_webhook_event_task
    with patch("app.workers.tasks.send_dm_task.delay") as mock_send_delay:
        process_webhook_event_task("evt_flow_01")
        assert mock_send_delay.call_count == 1
        job_id = mock_send_delay.call_args[0][0]

    # Verify execution and DMJob recorded
    job = db.query(DMJob).filter(DMJob.id == job_id).first()
    assert job is not None
    assert job.user_id == "usr_flow_user_1"
    assert job.status == "QUEUED"

    # 4. Execute send_dm_task with mocked PseudoGram client returning 202 Accepted
    mock_response_202 = MagicMock()
    mock_response_202.status_code = 202
    mock_response_202.json.return_value = {"dm_id": "dm_pseudogram_99", "status": "queued"}

    with patch("app.workers.tasks.rate_limiter.acquire_slot", return_value=(True, 0.0)), \
         patch("app.clients.pseudogram.PseudoGramClient.send_dm", return_value=mock_response_202), \
         patch("app.workers.tasks.reconcile_dm_status_task.apply_async") as mock_reconcile_async:
        
        send_dm_task(job_id)
        assert mock_reconcile_async.call_count == 1

    db.refresh(job)
    assert job.pseudogram_dm_id == "dm_pseudogram_99"
    assert job.status == "QUEUED"

    # 5. Execute reconcile_dm_status_task returning delivered
    mock_response_delivered = MagicMock()
    mock_response_delivered.status_code = 200
    mock_response_delivered.json.return_value = {
        "dm_id": "dm_pseudogram_99",
        "status": "delivered",
        "recipient_user_id": "usr_flow_user_1"
    }

    with patch("app.clients.pseudogram.PseudoGramClient.get_dm_status", return_value=mock_response_delivered):
        reconcile_dm_status_task(job_id)

    db.refresh(job)
    assert job.status == "SENT"


def test_duplicate_user_rule_prevention():
    db = TestingSyncSessionLocal()

    # Create Rule
    rule = Rule(id="rule_price_2", keyword="PRICE", dm_message="Price list message")
    db.add(rule)
    db.commit()

    # Event 1 from usr_repeat
    event1 = WebhookEvent(
        event_id="evt_rep_01",
        event_type="comment.created",
        payload={
            "event_id": "evt_rep_01",
            "event_type": "comment.created",
            "data": {
                "comment_id": "cmt_rep_01",
                "text": "PRICE info please",
                "from": {"user_id": "usr_repeat", "username": "repeat_user"}
            }
        },
        processed=False
    )
    db.add(event1)
    db.commit()

    with patch("app.workers.tasks.send_dm_task.delay"):
        process_webhook_event_task("evt_rep_01")

    # Event 2 from same usr_repeat with different comment & event_id
    event2 = WebhookEvent(
        event_id="evt_rep_02",
        event_type="comment.created",
        payload={
            "event_id": "evt_rep_02",
            "event_type": "comment.created",
            "data": {
                "comment_id": "cmt_rep_02",
                "text": "PRICE price PRICE",
                "from": {"user_id": "usr_repeat", "username": "repeat_user"}
            }
        },
        processed=False
    )
    db.add(event2)
    db.commit()

    with patch("app.workers.tasks.send_dm_task.delay") as mock_send_delay:
        process_webhook_event_task("evt_rep_02")
        # Second event should be blocked from sending duplicate DM!
        assert mock_send_delay.call_count == 0

    # Verify duplicate log entry recorded
    dup_log = db.query(DuplicateLog).filter(DuplicateLog.user_id == "usr_repeat").first()
    assert dup_log is not None
    assert dup_log.reason == "USER_RULE_DUPLICATE"


def test_comment_deleted_event():
    db = TestingSyncSessionLocal()

    rule = Rule(id="rule_price_3", keyword="PRICE", dm_message="Price list")
    db.add(rule)

    job = DMJob(
        id="job_to_cancel",
        user_id="usr_del",
        rule_id="rule_price_3",
        comment_id="cmt_to_delete",
        dm_message="Price list",
        idempotency_key="key_to_cancel",
        status="QUEUED"
    )
    db.add(job)

    ex = UserRuleExecution(
        user_id="usr_del",
        rule_id="rule_price_3",
        comment_id="cmt_to_delete",
        status="DISPATCHED"
    )
    db.add(ex)

    del_event = WebhookEvent(
        event_id="evt_del_01",
        event_type="comment.deleted",
        payload={
            "event_id": "evt_del_01",
            "event_type": "comment.deleted",
            "data": {"comment_id": "cmt_to_delete"}
        },
        processed=False
    )
    db.add(del_event)
    db.commit()

    process_webhook_event_task("evt_del_01")

    job = db.query(DMJob).filter(DMJob.id == "job_to_cancel").first()
    assert job.status == "CANCELLED"

    ex = db.query(UserRuleExecution).filter(UserRuleExecution.comment_id == "cmt_to_delete").first()
    assert ex.status == "CANCELLED_DELETED"
