# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Re-index papers (run whenever papers/ changes, then commit api/papers_index.json)
python scripts/index_papers.py

# Run locally (from repo root)
ANTHROPIC_API_KEY=sk-... uvicorn api.index:app --reload
# App available at http://localhost:8000
```

## Architecture

Single-file FastAPI backend (`api/index.py`) with a single-page frontend (`public/index.html`).

**RAG pipeline:**
1. `scripts/index_papers.py` runs locally, extracts text from `papers/*.pdf` with `pdfplumber`, chunks it (~400 words, 50-word overlap), and writes `api/papers_index.json`. This file is committed to the repo.
2. At cold start, `api/index.py` loads `papers_index.json` from the same directory and builds a `BM25Okapi` index (`rank_bm25`).
3. On `POST /search`, BM25 retrieves the top-5 scoring chunks for the query, which are sent as context to Claude (`claude-sonnet-4-6`).
4. The response includes the answer text and a deduplicated list of source paper names.

**Why JSON instead of runtime PDF processing:** Vercel's function bundle limit (~50 MB compressed) is easily exceeded when bundling multiple PDFs on top of large Python deps (pdfplumber + Pillow). Committing pre-extracted JSON sidesteps this entirely — the JSON is a few hundred KB and lives in `api/` so Vercel bundles it automatically without any `includeFiles` entry.

**Routing:** `GET /` serves `public/index.html` read directly from disk. `vercel.json` rewrites all requests to `api/index.py`. `GET /papers` returns the list of loaded papers for deployment verification.

## Deployment (Vercel)

Set `ANTHROPIC_API_KEY` as an environment variable in Vercel project settings. Make sure `api/papers_index.json` is committed before deploying. The `vercel.json` sets a 30-second timeout.
