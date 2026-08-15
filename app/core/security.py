import hmac
import hashlib
from app.core.config import settings
from app.core.logging import logger

def verify_webhook_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """
    Verifies HMAC-SHA256 signature from PseudoGram webhook.
    Header format: X-PseudoGram-Signature: sha256=<hex>
    Secret: PSEUDOGRAM_API_KEY
    """
    if not settings.PSEUDOGRAM_API_KEY:
        # If API key is not configured yet, log warning and allow for development/testing if needed,
        # but in strict mode verification should fail unless explicitly bypassed.
        logger.warning("PSEUDOGRAM_API_KEY is not configured; skipping signature check.")
        return True

    if not signature_header:
        logger.warning("Missing X-PseudoGram-Signature header.")
        return False

    prefix = "sha256="
    if signature_header.startswith(prefix):
        provided_hex = signature_header[len(prefix):]
    else:
        provided_hex = signature_header

    expected_hmac = hmac.new(
        key=settings.PSEUDOGRAM_API_KEY.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    )
    expected_hex = expected_hmac.hexdigest()

    is_valid = hmac.compare_digest(provided_hex.lower(), expected_hex.lower())
    if not is_valid:
        logger.warning("Invalid webhook signature: provided=%s, expected=%s", provided_hex, expected_hex)
    return is_valid
