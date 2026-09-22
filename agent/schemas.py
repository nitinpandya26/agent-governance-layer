from pydantic import BaseModel, Field
from typing import Literal


class AgentDecision(BaseModel):
    decision: Literal["approve", "reject", "escalate"]
    reasoning: str = Field(description="Why the agent reached this decision, in plain language")
    confidence: float = Field(ge=0.0, le=1.0)
    tools_called: list[str] = Field(default_factory=list)
    facts_relied_on: list[str] = Field(default_factory=list, description="Key facts that drove the decision")