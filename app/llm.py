"""Answer generation.

Two modes, same contract (answer text built ONLY from retrieved chunks):

1. LLM mode — when ``LLM_BASE_URL`` (+ ``LLM_MODEL``) are configured, POST to
   any OpenAI-compatible endpoint (vLLM, llama.cpp server, OpenAI, ...).
2. Extractive mode (default) — pick the sentences from the retrieved chunks
   that best match the question and stitch them together with citations.
   Fully offline, deterministic, and perfectly grounded by construction.
"""
from __future__ import annotations

import json
import urllib.request

from .config import settings
from .text import content_terms, split_sentences


def _extractive_answer(question: str, results: list[dict], max_sentences: int = 4) -> str:
    q_terms = set(content_terms(question))
    if not results:
        return ""
    # Only draw sentences from chunks that are competitive with the top hit —
    # a weak chunk sharing one word ('continuous' archiving vs 'continuous'
    # batching) must not leak into the answer.
    cutoff = 0.5 * results[0]["score"]
    pool = [r for r in results[:5] if r["score"] >= cutoff]
    scored: list[tuple[float, str, dict]] = []
    for r in pool:
        for sent in split_sentences(r["text"]):
            overlap = len(q_terms & set(content_terms(sent)))
            if overlap:
                scored.append((overlap * (0.5 + r["score"]), sent, r))
    if not scored:
        # Fall back to the opening of the best chunk rather than inventing text.
        top = results[0]
        first = split_sentences(top["text"])
        return (first[0] if first else top["text"][:300]) + f" [{top['source']}]"
    scored.sort(key=lambda x: -x[0])
    picked, seen = [], set()
    for _, sent, r in scored:
        if sent in seen:
            continue
        seen.add(sent)
        picked.append(f"{sent} [{r['source']}]")
        if len(picked) >= max_sentences:
            break
    return " ".join(picked)


def _llm_answer(question: str, results: list[dict]) -> str | None:
    if not settings.llm_base_url or not settings.llm_model:
        return None
    context = "\n\n".join(
        f"[{r['source']} — {r['heading']}]\n{r['text']}" for r in results[:4]
    )
    prompt = (
        "Answer the question using ONLY the context below. Cite sources like "
        "[source] after each claim. If the context does not contain the answer, "
        "say you do not know.\n\n"
        f"Context:\n{context}\n\nQuestion: {question}"
    )
    body = json.dumps({
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }).encode()
    req = urllib.request.Request(
        f"{settings.llm_base_url}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key or 'not-needed'}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None  # fall back to extractive rather than failing the request


def generate_answer(question: str, results: list[dict]) -> tuple[str, str]:
    """Returns (answer, mode) where mode is 'llm' or 'extractive'."""
    llm = _llm_answer(question, results)
    if llm:
        return llm, "llm"
    return _extractive_answer(question, results), "extractive"
