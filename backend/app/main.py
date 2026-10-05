from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .providers import get_provider
from .schemas import AnalyzeRequest, AnalysisResponse

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
MODE = os.getenv("ANALYSIS_MODE", "demo")
app = FastAPI(title="TruthLens API", version="0.1.0", description="Explainable misinformation and AI-writing analysis.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_origin_regex=r"https://.*\.vercel\.app", allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

def make_response(content: str) -> AnalysisResponse:
    provider = get_provider(MODE)
    claims = provider.analyze_claims(content)
    ai_likelihood, ai_assessment, ai_signals = provider.ai_signals(content)
    verdicts = [c.verdict for c in claims]
    if "Likely Misleading" in verdicts:
        verdict = "Likely Misleading"
    elif "Unverified" in verdicts:
        verdict = "Unverified"
    else:
        verdict = "Verified"

    # Weight the overall confidence toward the strongest evidence rather than
    # averaging away a high-confidence contradiction.
    confidence = round(max(c.confidence for c in claims) * 0.6 + sum(c.confidence for c in claims) / len(claims) * 0.4)
    risk = max(8, min(92, 100 - confidence + {"Verified": 0, "Unverified": 15, "Likely Misleading": 35}[verdict]))
    summary = {
        "Verified": "Live evidence supports the checked claim, but the original sources should still be reviewed for high-stakes decisions.",
        "Unverified": "Live sources were found, but they do not provide enough consistent evidence to confirm or contradict the claim.",
        "Likely Misleading": "The live evidence contains signals that conflict with or undermine the claim. Review the cited sources before sharing."
    }[verdict]
    return AnalysisResponse(verdict=verdict, risk_score=risk, summary=summary, claims=claims, ai_likelihood=ai_likelihood, ai_assessment=ai_assessment, ai_signals=ai_signals, analysis_mode=MODE, disclaimer=("Live mode uses Tavily web evidence and, when OPENAI_API_KEY is configured, an AI evidence judge. It is not a guarantee of truth, professional advice, or proof that text was AI-generated." if MODE == "live" else "Demo mode uses curated examples and heuristic language signals. It is not live web verification, professional advice, or proof that text was AI-generated."))

@app.get("/health")
def health(): return {"status": "ok", "analysis_mode": MODE}

@app.get("/api/sample", response_model=AnalyzeRequest)
def sample(): return AnalyzeRequest(content="URGENT: The Government of India has announced free laptops for every student from Class 1 to college. Fill out this form today or you will lose your chance. Share this message with everyone.")

@app.post("/api/analyze", response_model=AnalysisResponse)
def analyze(request: AnalyzeRequest):
    # Demo mode deliberately does not retrieve remote pages. It still returns an
    # explicit unverified result for a submitted URL, rather than implying it read it.
    if request.input_type == "url":
        return make_response(f"Article URL submitted for verification: {request.content}")
    return make_response(request.content)
