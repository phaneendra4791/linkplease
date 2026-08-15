from unittest.mock import patch

def test_webhook_ingestion_and_duplicate_event_handling(client):
    settings_patch = patch("app.api.webhook.verify_webhook_signature", return_value=True)
    task_patch = patch("app.services.webhook_service.process_webhook_event_task.delay")

    with settings_patch, task_patch as mock_task:
        payload = {
            "event_id": "evt_unique_1001",
            "event_type": "comment.created",
            "sent_at": "2026-08-10T09:14:22.481Z",
            "data": {
                "comment_id": "cmt_1001",
                "post_id": "post_1",
                "text": "PRICE please!",
                "from": {
                    "user_id": "usr_999",
                    "username": "testuser"
                }
            }
        }

        # First delivery -> 200 OK
        res1 = client.post("/webhook", json=payload)
        assert res1.status_code == 200
        assert res1.json()["duplicate"] is False
        assert mock_task.call_count == 1

        # Second delivery (Duplicate event_id) -> 200 OK, duplicate flag True
        res2 = client.post("/webhook", json=payload)
        assert res2.status_code == 200
        assert res2.json()["duplicate"] is True
        # Task should NOT be enqueued second time
        assert mock_task.call_count == 1

def test_stats_endpoint(client):
    res = client.get("/stats")
    assert res.status_code == 200
    data = res.json()
    assert "sent" in data
    assert "failed" in data
    assert "queued" in data
    assert "duplicates_blocked" in data
