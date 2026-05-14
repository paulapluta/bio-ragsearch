# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (from repo root)
ANTHROPIC_API_KEY=sk-... uvicorn api.index:app --reload

# App available at http://localhost:8000
```

## Architecture

Single-file FastAPI backend (`api/index.py`) with an embedded single-page frontend (`public/index.html`).

**RAG pipeline (runs at cold start):**
1. `_build_index()` iterates `papers/*.pdf`, extracts text with `pdfplumber`, splits into ~400-word chunks with 50-word overlap, and builds a `BM25Okapi` index from `rank_bm25`.
2. On `POST /search`, BM25 retrieves the top-5 scoring chunks for the query, which are sent as context to Claude (`claude-sonnet-4-6`) along with the original question.
3. The response includes the answer text and a deduplicated list of source paper names.

**Routing:** `GET /` serves `public/index.html` directly from FastAPI (not as a static mount). `vercel.json` rewrites all requests to `api/index.py`, so the same app handles both local dev and Vercel deployment.

**Path resolution:** `api/index.py` uses `os.path.dirname(os.path.abspath(__file__))` to navigate to the repo root, making `PAPERS_DIR` and `PUBLIC_DIR` work correctly regardless of the working directory at invocation.

## Deployment (Vercel)

Set `ANTHROPIC_API_KEY` as an environment variable in the Vercel project settings. Deploy via `vercel --prod` or by connecting the GitHub repo. The `vercel.json` sets a 30-second function timeout to accommodate cold-start PDF indexing + Claude API latency.
