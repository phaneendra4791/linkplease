import os
import hmac
import hashlib
from dotenv import load_dotenv

load_dotenv()

secret = os.getenv("PSEUDOGRAM_API_KEY")

body = '''{
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
}'''

signature = hmac.new(
    secret.encode("utf-8"),
    body.encode("utf-8"),
    hashlib.sha256
).hexdigest()

print("X-PseudoGram-Signature:")
print("sha256=" + signature)