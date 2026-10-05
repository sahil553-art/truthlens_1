"""Provider boundary: replace this demo provider with real LLM/search adapters later."""
from __future__ import annotations
import json
import re
import os
from abc import ABC, abstractmethod
from urllib.parse import urlparse
import httpx
from .schemas import AiSignal, Claim, Source

LAPTOP_PATTERNS = ("free laptop", "free laptops", "laptop for every student")
HEALTH_PATTERNS = ("150 minutes", "physical activity", "exercise every week")

class AnalysisProvider(ABC):
    @abstractmethod
    def analyze_claims(self, text: str) -> list[Claim]: ...
    @abstractmethod
    def ai_signals(self, text: str) -> tuple[int, str, list[AiSignal]]: ...

class DemoAnalysisProvider(AnalysisProvider):
    """Deterministic provider with explicit demo labels—never live fact-checking."""
    def analyze_claims(self, text: str) -> list[Claim]:
        cleaned = " ".join(text.split())
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", cleaned) if len(s.strip()) > 18]
        claims = []
        for sentence in (sentences[:3] or [cleaned[:280]]):
            lower = sentence.lower()
            if any(p in lower for p in LAPTOP_PATTERNS):
                claims.append(Claim(text=sentence, verdict="Likely Misleading", confidence=78, explanation="This broad benefit claim uses urgency and universal eligibility but gives no official scheme name, notification, or verifiable link.", sources=[Source(title="Government scheme information", publisher="MyScheme", url="https://www.myscheme.gov.in/", stance="context", snippet="Official scheme portal where eligibility and benefit details can be checked.", trust_note="Official government service portal"), Source(title="How to spot misinformation", publisher="PIB Fact Check", url="https://factcheck.pib.gov.in/", stance="context", snippet="Verify viral government-benefit messages through official channels before sharing.", trust_note="Government fact-checking unit")]))
            elif any(p in lower for p in HEALTH_PATTERNS):
                claims.append(Claim(text=sentence, verdict="Verified", confidence=88, explanation="The statement aligns with established public-health guidance, though individual needs can vary.", sources=[Source(title="Physical activity", publisher="World Health Organization", url="https://www.who.int/news-room/fact-sheets/detail/physical-activity", stance="supports", snippet="WHO recommends at least 150 minutes of moderate-intensity activity weekly for adults.", trust_note="International public-health authority")]))
            else:
                claims.append(Claim(text=sentence, verdict="Unverified", confidence=45, explanation="The demo evidence provider could not match this claim to a sufficiently specific, authoritative source. Check the original source and independent reporting.", sources=[Source(title="Verification checklist", publisher="International Fact-Checking Network", url="https://www.poynter.org/ifcn/", stance="context", snippet="Look for a primary source, publication date, full context, and independent corroboration.", trust_note="Research guidance; not evidence for the claim")]))
        return claims

    def ai_signals(self, text: str) -> tuple[int, str, list[AiSignal]]:
        words = re.findall(r"\b\w+\b", text)
        sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
        lower, score, signals = text.lower(), 30, []
        if len(words) > 90:
            score += 9; signals.append(AiSignal(name="Length and structure", detail="Long, consistently structured passages can be associated with assisted writing, but are common in human writing too.", impact="low"))
        if len(sentences) >= 3:
            lengths = [len(re.findall(r"\w+", s)) for s in sentences]
            if max(lengths) - min(lengths) < 9:
                score += 16; signals.append(AiSignal(name="Uniform sentence rhythm", detail="Sentence lengths are unusually consistent across the passage.", impact="medium"))
        found = [m for m in ("moreover", "furthermore", "in conclusion", "delve", "it is important to note", "comprehensive") if m in lower]
        if found:
            score += min(22, len(found) * 11); signals.append(AiSignal(name="Formulaic transitions", detail="Found repeated formal transition patterns often seen in generated or heavily edited text.", impact="medium"))
        if not signals:
            signals.append(AiSignal(name="Mixed writing signals", detail="No strong pattern was found in this short sample. More text improves only the estimate—not certainty.", impact="low"))
        score = min(score, 92)
        return score, "Some AI-like writing patterns detected" if score >= 55 else "No strong AI-like pattern detected", signals

def get_provider(mode: str) -> AnalysisProvider:
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if mode == "live" and key:
        return TavilyAnalysisProvider(key)
    return DemoAnalysisProvider()



class TavilyAnalysisProvider(DemoAnalysisProvider):
    """Live evidence provider: Tavily retrieves evidence; an LLM evaluates claim vs evidence."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-6-luna").strip()

    def analyze_claims(self, text: str) -> list[Claim]:
        cleaned = " ".join(text.split())
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", cleaned) if len(s.strip()) > 18]
        candidates = sentences[:3] or [cleaned[:280]]

        claims: list[Claim] = []
        for sentence in candidates:
            claims.append(self._verify_claim(sentence))
        return claims

    def _verify_claim(self, claim_text: str) -> Claim:
        evidence = self._search(claim_text)
        if not evidence["sources"]:
            return Claim(
                text=claim_text,
                verdict="Unverified",
                confidence=20,
                explanation="No usable live evidence was returned. The claim should not be treated as verified.",
                sources=[],
            )

        sources = evidence["sources"]

        # Prefer an LLM evidence judge when an OpenAI API key is configured.
        if self.openai_api_key:
            judged = self._llm_judge(claim_text, sources, evidence.get("answer", ""))
            if judged is not None:
                return self._claim_from_judgment(claim_text, sources, judged)

        # Safe fallback: preserve the deterministic live-evidence heuristic if no
        # LLM key is configured or if the LLM request fails.
        return self._heuristic_verify(claim_text, sources, evidence.get("answer", ""))

    def _claim_from_judgment(self, claim_text: str, sources: list[Source], judged: dict) -> Claim:
        verdict = str(judged.get("verdict", "Unverified"))
        if verdict == "Contradicted":
            verdict = "Likely Misleading"
        if verdict not in {"Verified", "Unverified", "Likely Misleading"}:
            verdict = "Unverified"

        try:
            confidence = max(0, min(100, int(judged.get("confidence", 50))))
        except (TypeError, ValueError):
            confidence = 50

        explanation = str(judged.get("explanation", "")).strip()
        if not explanation:
            explanation = "The AI evidence judge could not provide a concise explanation."

        support_indexes = set()
        for key in ("supporting_sources", "contradicting_sources"):
            values = judged.get(key, [])
            if isinstance(values, list):
                for value in values:
                    try:
                        support_indexes.add(int(value))
                    except (TypeError, ValueError):
                        pass

        # Mark source stance according to the judge's selected evidence.
        marked = []
        contradicting = set()
        supporting = set()
        if isinstance(judged.get("supporting_sources"), list):
            supporting = {int(x) for x in judged["supporting_sources"] if str(x).isdigit()}
        if isinstance(judged.get("contradicting_sources"), list):
            contradicting = {int(x) for x in judged["contradicting_sources"] if str(x).isdigit()}

        for idx, source in enumerate(sources, start=1):
            if idx in supporting:
                stance = "supports"
            elif idx in contradicting:
                stance = "conflicts"
            else:
                stance = "context"
            marked.append(source.model_copy(update={"stance": stance}))

        return Claim(
            text=claim_text,
            verdict=verdict,
            confidence=confidence,
            explanation=explanation,
            sources=marked,
        )

    def _llm_judge(self, claim: str, sources: list[Source], tavily_answer: str) -> dict | None:
        evidence_lines = []
        for idx, source in enumerate(sources, start=1):
            evidence_lines.append(
                f"[SOURCE {idx}]\n"
                f"Title: {source.title}\n"
                f"Publisher: {source.publisher}\n"
                f"URL: {source.url}\n"
                f"Snippet: {source.snippet}\n"
                f"Trust note: {source.trust_note}"
            )

        prompt = f"""
You are the evidence judge for TruthLens, a misinformation-verification system.

Evaluate ONLY whether the supplied evidence supports the user's claim. Do not use
your own world knowledge to fill missing evidence. A source being authoritative
does not automatically prove a claim; check whether its content actually addresses
the claim. Distinguish a direct contradiction from merely missing evidence.

USER CLAIM:
{claim}

TAVILY SYNTHESIS (research hint, not proof):
{tavily_answer[:2000]}

SEARCH EVIDENCE:
{chr(10).join(evidence_lines)}

Return ONLY valid JSON with exactly these fields:
{{
  "verdict": "Verified" | "Contradicted" | "Unverified",
  "confidence": integer from 0 to 100,
  "explanation": "2-4 concise sentences explaining the comparison between claim and evidence.",
  "supporting_sources": [source numbers],
  "contradicting_sources": [source numbers]
}}

Rules:
- Verified: credible evidence directly supports the claim.
- Contradicted: credible evidence directly conflicts with the claim.
- Unverified: evidence is insufficient, ambiguous, indirect, or conflicting.
- Never call a claim Verified merely because no source contradicts it.
- Never call a claim Contradicted merely because a source does not mention it.
- Use only source numbers that exist.
"""

        try:
            response = httpx.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.openai_model,
                    "input": [
                        {
                            "role": "system",
                            "content": "You are a strict fact-checking evidence judge. Output only JSON."
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "text": {"format": {"type": "json_object"}},
                    "max_output_tokens": 500,
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()

            output_text = payload.get("output_text", "")
            if not output_text:
                for item in payload.get("output", []):
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            output_text += content.get("text", "")

            if not output_text:
                return None

            parsed = json.loads(output_text)
            if not isinstance(parsed, dict):
                return None
            return parsed
        except (httpx.HTTPError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

    def _heuristic_verify(self, claim_text: str, sources: list[Source], answer: str) -> Claim:
        haystack = " ".join([
            answer.lower(),
            " ".join((s.snippet or "").lower() for s in sources),
            " ".join((s.title or "").lower() for s in sources),
        ])

        conflict_terms = (
            "false", "misleading", "incorrect", "not true", "untrue",
            "no evidence", "debunked", "fabricated", "fake claim",
            "unsupported", "does not exist", "there is no"
        )
        support_terms = (
            "confirmed", "officially announced", "according to the official",
            "supports the claim", "true", "verified", "reported by"
        )

        conflict_hits = sum(1 for term in conflict_terms if term in haystack)
        support_hits = sum(1 for term in support_terms if term in haystack)
        trusted_count = sum(1 for s in sources if "Higher-authority" in s.trust_note)

        if conflict_hits >= 2 and conflict_hits > support_hits:
            verdict = "Likely Misleading"
            confidence = min(90, 65 + conflict_hits * 7 + min(trusted_count * 5, 10))
            explanation = "The live evidence contains multiple signals that conflict with or undermine the claim."
        elif support_hits >= 2 and support_hits > conflict_hits and trusted_count:
            verdict = "Verified"
            confidence = min(90, 60 + support_hits * 6 + min(trusted_count * 6, 18))
            explanation = "The live search returned evidence that supports the claim, including a higher-authority source."
        else:
            verdict = "Unverified"
            confidence = min(78, 40 + len(sources) * 5 + min(trusted_count * 5, 10))
            explanation = "Relevant live sources were found, but the evidence is not strong enough to label the claim true or false."

        return Claim(
            text=claim_text,
            verdict=verdict,
            confidence=confidence,
            explanation=explanation,
            sources=sources,
        )

    def _search(self, claim: str) -> dict:
        try:
            response = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": claim,
                    "search_depth": "advanced",
                    "max_results": 5,
                    "include_answer": True,
                    "include_raw_content": False,
                },
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", [])
            sources: list[Source] = []

            for result in results[:5]:
                url = result.get("url", "")
                domain = urlparse(url).netloc.lower()
                trusted = any(
                    token in domain
                    for token in (
                        ".gov", ".gov.in", ".edu", "who.int",
                        "reuters.com", "apnews.com", "bbc.com",
                        "pib.gov.in", "mygov.in"
                    )
                )
                sources.append(
                    Source(
                        title=result.get("title") or domain or "Search result",
                        publisher=domain.replace("www.", "") or "Web source",
                        url=url,
                        stance="context",
                        snippet=(result.get("content") or "No preview available.")[:400],
                        trust_note=(
                            "Higher-authority domain"
                            if trusted
                            else "Review the original source and corroborate independently"
                        ),
                    )
                )

            return {"answer": payload.get("answer", ""), "sources": sources}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return {"answer": "", "sources": []}
