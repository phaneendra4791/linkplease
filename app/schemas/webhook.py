from typing import Optional
from pydantic import BaseModel, Field

class WebhookUser(BaseModel):
    user_id: str
    username: Optional[str] = None

class WebhookData(BaseModel):
    comment_id: str
    post_id: Optional[str] = None
    text: Optional[str] = None
    created_at: Optional[str] = None
    from_user: Optional[WebhookUser] = Field(None, alias="from")

    model_config = {
        "populate_by_name": True
    }

class WebhookPayload(BaseModel):
    event_id: str
    event_type: str
    sent_at: str
    data: WebhookData
