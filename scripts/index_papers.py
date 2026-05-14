#!/usr/bin/env python3
"""
Extract text from all PDFs in /papers and write api/papers_index.json.
Run this locally whenever the papers/ folder changes, then commit the result.

    python scripts/index_papers.py
"""
import json
import os
import sys

import pdfplumber

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS_DIR = os.path.join(ROOT, "papers")
OUTPUT = os.path.join(ROOT, "api", "papers_index.json")

CHUNK_SIZE = 400
CHUNK_OVERLAP = 50

_PLACEHOLDER_TITLES = {"untitled", "unknown", "no title", "none", ""}


def get_display_name(pdf_path: str, stem: str) -> str:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if pdf.metadata:
                title = (pdf.metadata.get("Title") or "").strip()
                if len(title) > 4 and title.lower() not in _PLACEHOLDER_TITLES:
                    return title
    except Exception:
        pass
    return stem


def extract_text(pdf_path: str) -> str:
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)


def chunk_text(text: str) -> list[str]:
    words = text.split()
    step = max(1, CHUNK_SIZE - CHUNK_OVERLAP)
    return [
        " ".join(words[i : i + CHUNK_SIZE])
        for i in range(0, len(words), step)
        if words[i : i + CHUNK_SIZE]
    ]


def main() -> None:
    pdf_files = sorted(f for f in os.listdir(PAPERS_DIR) if f.lower().endswith(".pdf"))
    if not pdf_files:
        print(f"No PDFs found in {PAPERS_DIR}", file=sys.stderr)
        sys.exit(1)

    corpus = []
    errors = 0
    for fname in pdf_files:
        path = os.path.join(PAPERS_DIR, fname)
        stem = fname[:-4]
        name = get_display_name(path, stem)
        try:
            chunks = chunk_text(extract_text(path))
            for chunk in chunks:
                corpus.append({"chunk": chunk, "paper": name})
            print(f"  OK  {fname}  →  '{name}'  ({len(chunks)} chunks)")
        except Exception as exc:
            print(f"FAIL  {fname}  →  {exc}", file=sys.stderr)
            errors += 1

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False)

    print(f"\n{len(corpus)} chunks from {len(pdf_files) - errors}/{len(pdf_files)} papers → {OUTPUT}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
