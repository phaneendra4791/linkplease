import hmac
import hashlib
from app.core.security import verify_webhook_signature
from app.core.config import settings

def test_signature_verification_valid():
    raw_body = b'{"event_id": "evt_123", "data": {"text": "hello"}}'
    secret = "test-api-key"
    settings.PSEUDOGRAM_API_KEY = secret

    computed_hmac = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    header = f"sha256={computed_hmac}"

    assert verify_webhook_signature(raw_body, header) is True

def test_signature_verification_invalid():
    raw_body = b'{"event_id": "evt_123"}'
    settings.PSEUDOGRAM_API_KEY = "test-api-key"
    header = "sha256=invalid_hex_digest"

    assert verify_webhook_signature(raw_body, header) is False

def test_signature_verification_missing_header():
    raw_body = b'{"event_id": "evt_123"}'
    settings.PSEUDOGRAM_API_KEY = "test-api-key"

    assert verify_webhook_signature(raw_body, None) is False
