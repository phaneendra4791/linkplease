import json
from fastapi import APIRouter, Request, Depends, HTTPException, status, Header, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_db
from app.core.security import verify_webhook_signature
from app.services.webhook_service import record_and_enqueue_webhook
from app.core.logging import logger
from app.schemas.webhook import WebhookPayload

router = APIRouter(tags=["Webhook"])


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def handle_webhook(
    request: Request,
    body: WebhookPayload = Body(..., description="Webhook payload from PseudoGram"),
    x_pseudogram_signature: str | None = Header(default=None),
    db: AsyncSession = Depends(get_async_db)
):
    raw_body = await request.body()
    signature_hdr = x_pseudogram_signature

    # HMAC Signature verification
    if not verify_webhook_signature(raw_body, signature_hdr):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error("Failed to parse webhook JSON body: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON body"
        )

    is_duplicate, event = await record_and_enqueue_webhook(db, payload)

    return {
        "status": "ok",
        "duplicate": is_duplicate,
        "event_id": payload.get("event_id")
    }