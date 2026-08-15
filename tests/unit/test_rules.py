import pytest
from app.services.rule_service import create_rule, get_all_rules
from app.schemas.rules import RuleCreate

def test_create_rule_endpoint(client):
    response = client.post(
        "/rules",
        json={"keyword": "PRICE", "dm_message": "Here is the price list."}
    )
    assert response.status_code == 201
    data = response.json()
    assert "rule_id" in data
    assert data["keyword"] == "PRICE"
    assert data["dm_message"] == "Here is the price list."

@pytest.mark.asyncio
async def test_rule_matching_substring_and_case_insensitive(test_db):
    rule_in = RuleCreate(keyword="PRICE", dm_message="Price list message")
    created = await create_rule(test_db, rule_in)
    assert created.rule_id is not None

    rules = await get_all_rules(test_db)
    assert len(rules) == 1

    rule = rules[0]
    comment_text_1 = "Can I get the price please?"
    comment_text_2 = "What is the PRICE?"
    comment_text_3 = "No keyword here"

    assert rule.keyword.lower() in comment_text_1.lower()
    assert rule.keyword.lower() in comment_text_2.lower()
    assert rule.keyword.lower() not in comment_text_3.lower()
