from typing import Literal
from pydantic import BaseModel, Field

class AnalyzeRequest(BaseModel):
    content: str = Field(min_length=12, max_length=12000)
    input_type: Literal["text", "url"] = "text"

class Source(BaseModel):
    title: str
    publisher: str
    url: str
    stance: Literal["supports", "conflicts", "context"]
    snippet: str
    trust_note: str

class Claim(BaseModel):
    text: str
    verdict: Literal["Verified", "Unverified", "Likely Misleading"]
    confidence: int = Field(ge=0, le=100)
    explanation: str
    sources: list[Source]

class AiSignal(BaseModel):
    name: str
    detail: str
    impact: Literal["low", "medium", "high"]

class AnalysisResponse(BaseModel):
    verdict: Literal["Verified", "Unverified", "Likely Misleading"]
    risk_score: int = Field(ge=0, le=100)
    summary: str
    claims: list[Claim]
    ai_likelihood: int = Field(ge=0, le=100)
    ai_assessment: str
    ai_signals: list[AiSignal]
    analysis_mode: str
    disclaimer: str
