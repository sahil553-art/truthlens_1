# TruthLens

TruthLens is a beginner-friendly full-stack MVP for checking news, WhatsApp forwards, articles, and URLs. It extracts checkable claims, shows evidence context, gives an explainable verdict, and estimates whether text has characteristics associated with AI-generated writing.

> TruthLens is a research assistant, not a final arbiter of truth. Its AI-text estimate is a likelihood signal, never proof.

## What it does

- Paste text into a clean analysis workspace
- Extract individual factual claims
- Show **Verified / Unverified / Likely Misleading** with explanations
- Show source cards, risk score, and AI-writing signals
- Run in **demo mode without API keys**

## Project layout

```
TruthLens/
  backend/       FastAPI API and analysis providers
  frontend/      React + Tailwind user interface
  samples/       Ready-to-paste demo inputs
```

## Quick start

Open two terminals in this project folder.

### Terminal 1: backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

If PowerShell blocks activation, first run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Terminal 2: frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open the address shown in Terminal 2 (usually `http://localhost:5173`). Click **Try sample analysis** to see the complete experience.

## Optional API configuration

The default `ANALYSIS_MODE=demo` needs no keys. To enable live evidence cards, set `ANALYSIS_MODE=live` and add a Tavily API key. Live mode uses Tavily advanced search, multiple source results, Tavily answer synthesis, and conservative evidence interpretation. A source result is evidence to inspect—not automatic proof that a claim is true.

```env
ANALYSIS_MODE=live
OPENAI_API_KEY=
TAVILY_API_KEY=your_key_here
```

## API documentation

With the backend running, visit [http://localhost:8000/docs](http://localhost:8000/docs).

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Verify the backend and active mode |
| `POST` | `/api/analyze` | Analyze text or a URL |
| `GET` | `/api/sample` | Get a presentation-ready example |

## Four-person team split

1. Frontend visual polish and mobile layout.
2. Source research and evidence provider improvements.
3. Claim extraction and AI-writing-signal improvements.
4. Testing, pitch, and presentation.

## Before presenting

- Keep the backend terminal running.
- Start on the sample analysis, then paste one short claim live.
- Describe the AI result as a “likelihood, not proof.”
- Explain that production use requires live, cited-source retrieval and human review for high-stakes claims.


## Live fact-checking flow

When `ANALYSIS_MODE=live`, TruthLens:
1. Splits the submitted text into checkable statements.
2. Searches Tavily with each statement using advanced search.
3. Retrieves up to five source results plus Tavily's answer synthesis.
4. Looks for supporting/conflicting signals and higher-authority domains.
5. Returns `Verified`, `Unverified`, or `Likely Misleading` conservatively.

The result is an evidence-assistance system, not a perfect truth oracle. Always inspect the linked sources.


## AI evidence judging

Live mode uses Tavily to retrieve web evidence. If `OPENAI_API_KEY` is configured,
TruthLens sends each claim plus the retrieved source snippets to an LLM evidence
judge. The judge returns a structured verdict, confidence, explanation, and the
source numbers that support or contradict the claim. If the OpenAI key is absent
or the judge request fails, TruthLens falls back to its conservative live-evidence
heuristic rather than pretending an AI judgment was made.

Backend `.env` example:

```env
ANALYSIS_MODE=live
TAVILY_API_KEY=your_tavily_key
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-6-luna
```

Restart the backend after changing `.env`:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

The OpenAI API is called server-side; never put the API key in the React frontend
or commit `.env` to Git.
