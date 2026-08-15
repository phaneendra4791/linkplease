import time
import math
from celery import shared_task
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from app.workers.celery_app import celery_app
from app.db.database import SyncSessionLocal
from app.db.models import WebhookEvent, Rule, UserRuleExecution, DMJob, DuplicateLog, utc_now
from app.clients.pseudogram import PseudoGramClient
from app.workers.rate_limiter import RedisRateLimiter
from app.core.config import settings
from app.core.logging import logger

rate_limiter = RedisRateLimiter()

@celery_app.task(bind=True, max_retries=10, default_retry_delay=5)
def process_webhook_event_task(self, event_id: str):
    db = SyncSessionLocal()
    try:
        event = db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()
        if not event or event.processed:
            return

        payload = event.payload
        event_type = event.event_type

        if event_type == "comment.deleted":
            data = payload.get("data", {})
            comment_id = data.get("comment_id")
            if comment_id:
                # Cancel queued DM jobs for deleted comment
                queued_jobs = db.query(DMJob).filter(
                    DMJob.comment_id == comment_id,
                    DMJob.status == "QUEUED"
                ).all()
                for job in queued_jobs:
                    job.status = "CANCELLED"
                    job.last_error = "Comment deleted before DM send"
                
                # Mark execution status as CANCELLED_DELETED
                executions = db.query(UserRuleExecution).filter(
                    UserRuleExecution.comment_id == comment_id,
                    UserRuleExecution.status == "DISPATCHED"
                ).all()
                for ex in executions:
                    ex.status = "CANCELLED_DELETED"

            event.processed = True
            db.commit()
            return

        if event_type == "comment.created":
            data = payload.get("data", {})
            comment_id = data.get("comment_id")
            comment_text = data.get("text", "") or ""
            from_user = data.get("from", {}) or {}
            user_id = from_user.get("user_id")

            if not user_id or not comment_id:
                event.processed = True
                db.commit()
                return

            rules = db.query(Rule).all()
            matching_rules = [r for r in rules if r.keyword.lower() in comment_text.lower()]

            for rule in matching_rules:
                # Attempt atomic insertion of execution to enforce 1-DM-per-user-rule
                execution = UserRuleExecution(
                    user_id=user_id,
                    rule_id=rule.id,
                    comment_id=comment_id,
                    status="DISPATCHED"
                )
                db.add(execution)
                try:
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    # User already received this rule's DM! Record duplicate log.
                    dup_log = DuplicateLog(
                        reason="USER_RULE_DUPLICATE",
                        event_id=event_id,
                        user_id=user_id,
                        rule_id=rule.id
                    )
                    db.add(dup_log)
                    db.commit()
                    logger.info("Blocked duplicate DM for user_id=%s, rule_id=%s", user_id, rule.id)
                    continue

                # Execution created successfully -> create DM Job
                idempotency_key = f"dm_job_{user_id}_{rule.id}"
                dm_job = DMJob(
                    user_id=user_id,
                    rule_id=rule.id,
                    comment_id=comment_id,
                    dm_message=rule.dm_message,
                    idempotency_key=idempotency_key,
                    status="QUEUED"
                )
                db.add(dm_job)
                db.commit()

                # Dispatch send task
                send_dm_task.delay(dm_job.id)

            event.processed = True
            db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Error processing webhook event %s: %s", event_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=15, default_retry_delay=5)
def send_dm_task(self, job_id: str):
    db = SyncSessionLocal()
    try:
        job = db.query(DMJob).filter(DMJob.id == job_id).first()
        if not job or job.status != "QUEUED":
            return

        # Check Redis sliding window rate limiter
        allowed, wait_time = rate_limiter.acquire_slot()
        if not allowed:
            logger.info("Rate limit triggered for job %s. Waiting %f seconds.", job_id, wait_time)
            raise self.retry(countdown=int(wait_time))

        client = PseudoGramClient()
        response = client.send_dm(
            recipient_user_id=job.user_id,
            message=job.dm_message,
            comment_id=job.comment_id,
            idempotency_key=job.idempotency_key
        )

        job.attempts += 1
        job.updated_at = utc_now()

        if response.status_code == 202:
            data = response.json()
            job.pseudogram_dm_id = data.get("dm_id")
            db.commit()
            # Schedule reconciliation check in 5 seconds
            reconcile_dm_status_task.apply_async(args=[job.id], countdown=5)
            return

        if response.status_code == 429:
            retry_after_hdr = response.headers.get("Retry-After")
            try:
                countdown = int(retry_after_hdr) if retry_after_hdr else 60
            except ValueError:
                countdown = 60
            job.last_error = f"429 Rate Limited (Retry-After {countdown}s)"
            db.commit()
            raise self.retry(countdown=countdown)

        if response.status_code == 500:
            job.last_error = f"500 Internal Error (Attempt {job.attempts})"
            if job.attempts >= settings.MAX_DM_RETRIES:
                job.status = "FAILED"
                db.commit()
                logger.error("Job %s failed permanently after max retries (500).", job_id)
            else:
                backoff = min(60, 2 ** job.attempts)
                db.commit()
                raise self.retry(countdown=backoff)
            return

        if response.status_code == 400:
            job.status = "FAILED"
            job.last_error = f"400 Invalid Request: {response.text}"
            db.commit()
            logger.error("Job %s failed with 400 Bad Request.", job_id)
            return

        # Unexpected status
        job.last_error = f"Unexpected status {response.status_code}: {response.text}"
        if job.attempts >= settings.MAX_DM_RETRIES:
            job.status = "FAILED"
            db.commit()
        else:
            db.commit()
            raise self.retry(countdown=5)
    except self.Retry:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Exception in send_dm_task for job %s: %s", job_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=20, default_retry_delay=5)
def reconcile_dm_status_task(self, job_id: str):
    db = SyncSessionLocal()
    try:
        job = db.query(DMJob).filter(DMJob.id == job_id).first()
        if not job or job.status != "QUEUED" or not job.pseudogram_dm_id:
            return

        client = PseudoGramClient()
        response = client.get_dm_status(job.pseudogram_dm_id)

        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            if status == "delivered":
                job.status = "SENT"
                job.updated_at = utc_now()
                db.commit()
                logger.info("Job %s confirmed DELIVERED by PseudoGram.", job_id)
                return
            elif status == "failed":
                if job.attempts < settings.MAX_DM_RETRIES:
                    logger.warning("Job %s DM failed post-acceptance. Retrying send.", job_id)
                    job.pseudogram_dm_id = None
                    db.commit()
                    send_dm_task.delay(job.id)
                else:
                    job.status = "FAILED"
                    job.last_error = "PseudoGram delivery failed after max retries"
                    job.updated_at = utc_now()
                    db.commit()
                return
            elif status == "queued":
                # Still queued on PseudoGram side, poll again in 5 seconds
                db.commit()
                raise self.retry(countdown=5)
        else:
            # Server error on polling, retry polling in 5 seconds
            raise self.retry(countdown=5)
    except self.Retry:
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Exception in reconcile_dm_status_task for job %s: %s", job_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()
