# LinkPlease Tech Intern — Reliable Comment-to-DM Automation Backend

A high-reliability, production-grade backend implementation of the Instagram comment-to-DM automation engine built for the **LinkPlease Tech Intern Assignment**.

Designed specifically to handle hostile external API conditions: redelivered webhooks, out-of-order events, HTTP 500 internal errors, 429 rate limits (10 reqs/60s), asynchronous 202 delivery status reconciliations, and comment deletions.

---

## 🏗 Architecture & Stack

```text
                     +---------------------+
                     |  PseudoGram API     |
                     |  (Hostile External) |
                     +----------+----------+
                                |
             Webhook (POST)     |     DM API (POST/GET)
        HMAC SHA-256 Signature  |     X-API-Key, Idempotency-Key
                                v
                     +---------------------+
                     |    FastAPI App      |
                     |  /webhook  /rules   |
                     |       /stats        |
                     +----+-----------+----+
                          |           |
             Async DB     |           | Enqueue Tasks
             Operations   v           v
                    +-------+       +-------+
                    |  PG   |       | Redis |
                    | (DB)  |       +---+---+
                    +-------+           |
                                        v
                                +---------------+
                                | Celery Worker |
                                | - Rate Limit  |
                                | - DM Sender   |
                                | - Reconcile   |
                                +---------------+
```

### Technology Stack
- **Language & Core**: Python 3.12, FastAPI, Pydantic v2
- **Database**: PostgreSQL 16, SQLAlchemy 2.x, Alembic migrations, `asyncpg` + `psycopg2`
- **Background Queue & Rate Limiter**: Redis 7, Celery 5.3, Redis Sliding Window Rate Limiter
- **HTTP Client**: `httpx`
- **Testing**: `pytest`, `pytest-asyncio`, `aiosqlite`
- **Containerization**: Docker & Docker Compose

---

## ⚡ Non-Negotiable API Endpoints

### 1. `POST /rules`
Creates a keyword rule for automated DM responses.
- **Matching Logic**: Case-insensitive substring matching (`lower(keyword) in lower(comment_text)`). Supports arbitrary rules.
- **Request Body**:
  ```json
  {
    "keyword": "PRICE",
    "dm_message": "Here is our official price list: https://example.com/prices"
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "rule_id": "3b29a1b0-7f2e-4b10-8b1e-29f123456789",
    "keyword": "PRICE",
    "dm_message": "Here is our official price list: https://example.com/prices"
  }
  ```

### 2. `POST /webhook`
Receives comment events from PseudoGram.
- **Performance**: Validates request, records event, enqueues background worker task, and returns `HTTP 200 OK` in < 50ms (well under the 5-second deadline).
- **HMAC Signature Verification**: Verifies `X-PseudoGram-Signature: sha256=<hex>` header against raw request body using `PSEUDOGRAM_API_KEY`.
- **Event Idempotency**: DB `UNIQUE(event_id)` constraint drops redelivered events instantly without duplicating processing.
- **Request Body Example**:
  ```json
  {
    "event_id": "evt_01J8ZQ4K2N7RXA",
    "event_type": "comment.created",
    "sent_at": "2026-08-10T09:14:22.481Z",
    "data": {
      "comment_id": "cmt_9f2a7c",
      "post_id": "post_44de1b",
      "text": "PRICE please 🙏",
      "created_at": "2026-08-10T09:14:21.900Z",
      "from": {
        "user_id": "usr_3b91fe",
        "username": "arjun.shoots"
      }
    }
  }
  ```

### 3. `GET /stats`
Reports live statistical metrics strictly derived from persistent PostgreSQL state.
- **Response `200 OK`**:
  ```json
  {
    "sent": 142,
    "failed": 3,
    "queued": 8,
    "duplicates_blocked": 57
  }
  ```
- **Definitions**:
  - `sent`: DMs confirmed as `delivered` via PseudoGram status reconciliation (`GET /v1/dm/{dm_id}`).
  - `failed`: DMs permanently failed after retry exhaustion or malformed request (400).
  - `queued`: DMs waiting to be dispatched or awaiting status reconciliation.
  - `duplicates_blocked`: DMs prevented due to 1-DM-per-user-rule uniqueness constraints or duplicate event redeliveries.

---

## 🔒 Reliability & Invariants

1. **Duplicate DM Prevention (1-DM-Per-User-Rule)**:
   - Database constraint `UNIQUE (user_id, rule_id)` on `user_rule_executions`.
   - Protects against concurrent processing where multiple comments arrive from the same user simultaneously.

2. **Strict 10 reqs/60s Rate Limiting**:
   - Implemented via a Redis sliding-window algorithm (`zremrangebyscore`, `zcard`, `zadd`).
   - Requests are throttled and Celery tasks rescheduled dynamically before sending HTTP requests to PseudoGram.

3. **HTTP Failure Handling**:
   - `500 Internal Error`: Bounded exponential backoff up to 5 retries.
   - `429 Rate Limited`: Respects `Retry-After` header and reschedules Celery task countdown.
   - `400 Bad Request`: Marked as `FAILED` permanently without blind retrying.
   - `202 Accepted`: Tracked as `QUEUED`, deterministic `Idempotency-Key` (`dm_job_{user_id}_{rule_id}`) passed, reconciled via polling `GET /v1/dm/{dm_id}` until `delivered` or `failed`.

4. **`comment.deleted` Events**:
   - If a `comment.deleted` event arrives while a DM job is still `QUEUED`, the job is marked `CANCELLED` so no DM is dispatched.

---

## 🚀 Environment Variables

Copy `.env.example` to `.env`:

```env
APP_ENV=development
LOG_LEVEL=INFO

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/linkplease
SYNC_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/linkplease
REDIS_URL=redis://localhost:6379/0

PSEUDOGRAM_BASE_URL=https://pseudogram-api.onrender.com
PSEUDOGRAM_API_KEY=your_pseudogram_api_key_here
```

---

## 🐳 Running with Docker Compose

Start the full stack (FastAPI App, Celery Worker, PostgreSQL, Redis, Alembic Migrations):

```bash
docker compose up --build
```

Endpoints will be available at:
- Web App: `http://localhost:8000`
- Health Check: `http://localhost:8000/healthz`
- Swagger Docs: `http://localhost:8000/docs`

---

## 🧪 Running Tests

Run the full pytest suite (Unit, Integration, and Assignment E2E flows):

```bash
python -m pytest -v
```

---

## 📋 Failure Scenarios

See [FAILURES.md](file:///c:/Users/phane/Desktop/linkplease/FAILURES.md) for detailed analysis of 4 concrete failure scenarios and mitigation mechanisms.