import os
import anthropic
import pdfplumber
from rank_bm25 import BM25Okapi
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS_DIR = os.path.join(_BASE_DIR, "papers")
PUBLIC_DIR = os.path.join(_BASE_DIR, "public")


def _get_display_name(pdf_path: str, stem: str) -> str:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if pdf.metadata:
                title = (pdf.metadata.get("Title") or "").strip()
                if len(title) > 4:
                    return title
    except Exception:
        pass
    return stem


def _extract_text(pdf_path: str) -> str:
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)


def _chunk_text(text: str, size: int = 400, overlap: int = 50) -> list[str]:
    words = text.split()
    step = max(1, size - overlap)
    return [
        " ".join(words[i : i + size])
        for i in range(0, len(words), step)
        if words[i : i + size]
    ]


# Corpus and BM25 index — built once at cold start
_corpus: list[tuple[str, str]] = []  # (chunk, paper_display_name)
_bm25: BM25Okapi | None = None


def _build_index() -> None:
    global _corpus, _bm25
    if not os.path.isdir(PAPERS_DIR):
        print(f"[bioRAGsearch] papers dir not found: {PAPERS_DIR}")
        return
    for fname in sorted(os.listdir(PAPERS_DIR)):
        if not fname.lower().endswith(".pdf"):
            continue
        path = os.path.join(PAPERS_DIR, fname)
        name = _get_display_name(path, fname[:-4])
        try:
            for chunk in _chunk_text(_extract_text(path)):
                _corpus.append((chunk, name))
        except Exception as exc:
            print(f"[bioRAGsearch] skipped {fname}: {exc}")
    if _corpus:
        _bm25 = BM25Okapi([c[0].lower().split() for c in _corpus])
        print(f"[bioRAGsearch] indexed {len(_corpus)} chunks from {PAPERS_DIR}")


_build_index()


class SearchRequest(BaseModel):
    query: str


@app.get("/")
async def root() -> HTMLResponse:
    html_path = os.path.join(PUBLIC_DIR, "index.html")
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.post("/search")
async def search(req: SearchRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not set")

    # Retrieve top-5 chunks with BM25
    context_text = ""
    sources: list[str] = []

    if _bm25 and _corpus:
        scores = _bm25.get_scores(query.lower().split())
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:5]
        hits = [(i, scores[i]) for i in ranked if scores[i] > 0]

        if hits:
            seen: set[str] = set()
            parts = []
            for idx, _ in hits:
                chunk, paper = _corpus[idx]
                parts.append(f"[{paper}]\n{chunk}")
                seen.add(paper)
            context_text = "\n\n---\n\n".join(parts)
            sources = list(seen)

    if not context_text:
        context_text = "No directly relevant passages were found in the available papers."

    prompt = (
        "You are a biomedical research assistant. "
        "Answer the following question using the provided excerpts from research papers. "
        "Be precise and scientific. Cite the paper names shown in brackets when referencing findings. "
        "If the excerpts do not contain enough information, say so clearly.\n\n"
        f"Question: {query}\n\n"
        f"Context:\n{context_text}"
    )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    return {"answer": message.content[0].text, "sources": sources}
