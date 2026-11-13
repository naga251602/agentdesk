"""Text utilities: tokenisation, stopwords, markdown-aware chunking."""
from __future__ import annotations

import re

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "what", "which", "who", "whom", "how", "why", "when", "where", "can",
    "could", "should", "would", "do", "does", "did", "i", "you", "he", "she",
    "it", "we", "they", "my", "your", "his", "her", "its", "our", "their",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "as", "and",
    "or", "but", "if", "then", "so", "than", "too", "very", "just", "me",
    "him", "them", "this", "that", "these", "those", "am", "into", "about",
    "over", "under", "between", "through", "during", "before", "after",
}

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_\-\.]*")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _stem(token: str) -> str:
    """Very light suffix stemming so 'connecting' matches 'connect',
    'lists' matches 'list', 'indexes' matches 'index', etc."""
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def content_terms(text: str) -> list[str]:
    """Tokens minus stopwords, lightly stemmed — the terms that carry meaning."""
    return [_stem(t) for t in tokenize(text)
            if t not in STOPWORDS and len(t) > 1]


def split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text.replace("\n", " "))
    return [p.strip() for p in parts if len(p.strip()) > 15]


def chunk_document(text: str, chunk_tokens: int = 512, overlap: int = 64) -> list[dict]:
    """Split markdown into chunks: one per heading section, windowed when a
    section is longer than ``chunk_tokens``. Returns dicts with text + heading."""
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []
    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines)))
            current_heading = m.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines or current_heading:
        sections.append((current_heading, "\n".join(current_lines)))

    chunks: list[dict] = []
    for heading, body in sections:
        body = body.strip()
        if not body:
            continue
        words = body.split()
        if len(words) <= chunk_tokens:
            chunks.append({"heading": heading, "text": body})
            continue
        step = max(1, chunk_tokens - overlap)
        for start in range(0, len(words), step):
            piece = " ".join(words[start:start + chunk_tokens])
            if piece:
                chunks.append({"heading": heading, "text": piece})
            if start + chunk_tokens >= len(words):
                break
    return chunks
