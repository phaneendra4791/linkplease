from typing import Any, Dict, Optional
import httpx
from app.core.config import settings
from app.core.logging import logger

class PseudoGramClient:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or settings.PSEUDOGRAM_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.PSEUDOGRAM_API_KEY

    def _get_headers(self, idempotency_key: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def send_dm(self, recipient_user_id: str, message: str, comment_id: str, idempotency_key: Optional[str] = None) -> httpx.Response:
        url = f"{self.base_url}/v1/dm/send"
        payload = {
            "recipient_user_id": recipient_user_id,
            "message": message,
            "comment_id": comment_id
        }
        headers = self._get_headers(idempotency_key=idempotency_key)
        
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload, headers=headers)
            logger.info("send_dm response status=%d body=%s", response.status_code, response.text)
            return response

    def get_dm_status(self, dm_id: str) -> httpx.Response:
        url = f"{self.base_url}/v1/dm/{dm_id}"
        headers = self._get_headers()
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
            logger.info("get_dm_status id=%s status=%d body=%s", dm_id, response.status_code, response.text)
            return response
