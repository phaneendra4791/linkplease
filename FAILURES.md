# LinkPlease Backend — Engineering Failure Analysis (`FAILURES.md`)

This document details four concrete edge-case failure scenarios in the LinkPlease backend system, explaining exact conditions, root causes, current mitigations, and long-term elimination plans.

---

### Scenario 1: Ephemeral Rate-Limiter State Loss during Redis Restart

- **What can go wrong**: If the Redis container or process restarts during high-volume webhook intake, the sliding-window rate limiter state stored in the `rate_limit:dm_send` Redis sorted set is wiped out.
- **Under what conditions**: Sudden Redis process crash, container eviction, or host reboot under heavy comment volume.
- **Why it happens**: Sliding window timestamps are tracked in ephemeral Redis memory. Upon container restart, the rate counter starts from 0, allowing up to 10 immediate API requests to PseudoGram before rebuilding historical state. If burst traffic arrives during this window, requests could temporarily exceed PseudoGram's 10 req/60s rate limit.
- **Current Mitigation**: The Celery task worker catches HTTP `429 Rate Limited` responses from PseudoGram, parses the `Retry-After` header, updates task error state, and reschedules the task with exact countdown backoff (`raise self.retry(countdown=retry_after)`).
- **Full Elimination Plan**: Enable durable Redis AOF (`appendonly yes`) with `fsync=everysec`, or implement PostgreSQL table-backed distributed sliding window locks with transaction isolation.

---

### Scenario 2: Worker Death (SIGKILL / OOM) Between HTTP 202 Acceptance and DB Persistence

- **What can go wrong**: Celery worker process receives `SIGKILL` or suffers an Out-Of-Memory (OOM) eviction immediately after PseudoGram returns `HTTP 202 Accepted` but before the worker writes `pseudogram_dm_id` to PostgreSQL.
- **Under what conditions**: Host OOM event, server force-shutdown, or unhandled worker crashes during the millisecond execution window after HTTP response receipt.
- **Why it happens**: Celery uses late task acknowledgements (`task_acks_late=True`), causing the unacknowledged task to be re-delivered to another worker. When the new worker executes `send_dm_task`, it attempts to resend the DM for the same job.
- **Current Mitigation**: Every DM request includes a deterministic `Idempotency-Key` header (`dm_job_{user_id}_{rule_id}`). When retried, PseudoGram recognizes the idempotency key and returns the original `dm_id` rather than sending a duplicate DM to the recipient.
- **Full Elimination Plan**: Implement a two-phase transactional outbox pattern where pre-send intent state is persisted before network dispatch, paired with strict idempotency key tracking across worker restarts.

---

### Scenario 3: Reconciliation Queue Starvation Under Heavy Burst Traffic

- **What can go wrong**: Delivery reconciliation (`GET /v1/dm/{dm_id}`) polling tasks experience processing delays when hundreds of comment webhooks arrive simultaneously.
- **Under what conditions**: Sustained traffic spikes (e.g., 500 comment webhooks arriving within 10 seconds).
- **Why it happens**: Webhook ingestion tasks (`process_webhook_event_task`) and status reconciliation tasks (`reconcile_dm_status_task`) share the same Celery default task queue. High volume webhook ingestion fills worker queues, causing reconciliation tasks to wait behind pending webhooks.
- **Current Mitigation**: `/stats` reporting strictly counts confirmed `delivered` DMs as `sent`, maintaining 100% statistical accuracy under queue delays without falsely marking accepted DMs as sent.
- **Full Elimination Plan**: Separate Celery task queues into dedicated queues (`webhooks` queue, `dm_send` queue, `reconciliation` queue) with separate worker process pools and explicit task priorities.

---

### Scenario 4: Comment Deletion Race Condition (`comment.deleted` Arriving Post-Delivery)

- **What can go wrong**: A user posts a matching comment, receives a DM, and deletes their comment immediately afterward. A `comment.deleted` event arrives after the DM status is already `delivered`.
- **Under what conditions**: Rapid comment deletion by the user within seconds of posting.
- **Why it happens**: The DM was already dispatched and confirmed `delivered` by PseudoGram before the `comment.deleted` event hit the `/webhook` endpoint.
- **Current Mitigation**: If `comment.deleted` arrives while a DM job is still pending/queued in PostgreSQL, the system cancels the job (`status = 'CANCELLED'`) and marks execution as `CANCELLED_DELETED`, preventing unsent DMs from being delivered.
- **Full Elimination Plan**: Introduce a configurable artificial queue delay (e.g., 5-second buffer window) before DM dispatch to allow potential deletion events to arrive first, or integrate an out-of-band DM recall API if supported by the platform.
