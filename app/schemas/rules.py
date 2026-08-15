from pydantic import BaseModel, Field

class RuleCreate(BaseModel):
    keyword: str = Field(..., description="Keyword to trigger DM response (case-insensitive, substring match)")
    dm_message: str = Field(..., description="Message to DM to the user")

class RuleResponse(BaseModel):
    rule_id: str
    keyword: str
    dm_message: str

    model_config = {
        "from_attributes": True
    }
