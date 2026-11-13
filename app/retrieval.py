"""Hybrid retrieval: BM25 (lexical) + TF cosine (dense stand-in), fused.

The fusion shape mirrors the production design (BM25 + dense embeddings +
reranking into pgvector). The dense side here is a term-vector cosine so the
system runs offline with no model downloads; swap in sentence-transformers /
pgvector by implementing the same ``search`` interface (see README).
"""
from __future__ import annotations

import math
from collections import Counter

from .text import content_terms, tokenize


class Chunk:
    __slots__ = ("chunk_id", "doc_id", "source", "heading", "text", "terms", "tf")

    def __init__(self, chunk_id: str, doc_id: str, source: str, heading: str, text: str):
        self.chunk_id = chunk_id
        self.doc_id = doc_id
        self.source = source
        self.heading = heading
        self.text = text
        self.terms = content_terms(text)
        self.tf = Counter(self.terms)


class HybridIndex:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self._df: Counter = Counter()
        self._avg_len = 0.0

    def __len__(self) -> int:
        return len(self.chunks)

    def clear(self) -> None:
        self.chunks = []
        self._df = Counter()
        self._avg_len = 0.0

    def add(self, chunk: Chunk) -> None:
        self.chunks.append(chunk)
        for term in set(chunk.terms):
            self._df[term] += 1
        total = sum(len(c.terms) for c in self.chunks)
        self._avg_len = total / max(1, len(self.chunks))

    # -- scoring ---------------------------------------------------------
    def _idf(self, term: str) -> float:
        n = len(self.chunks)
        df = self._df.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _bm25(self, q_terms: list[str], chunk: Chunk, k1: float = 1.5, b: float = 0.75) -> float:
        if not chunk.terms:
            return 0.0
        dl = len(chunk.terms)
        score = 0.0
        for term in q_terms:
            tf = chunk.tf.get(term, 0)
            if tf == 0:
                continue
            denom = tf + k1 * (1 - b + b * dl / max(1.0, self._avg_len))
            score += self._idf(term) * (tf * (k1 + 1)) / denom
        return score

    @staticmethod
    def _cosine(q_tf: Counter, c_tf: Counter) -> float:
        if not q_tf or not c_tf:
            return 0.0
        dot = sum(q_tf[t] * c_tf.get(t, 0) for t in q_tf)
        nq = math.sqrt(sum(v * v for v in q_tf.values()))
        nc = math.sqrt(sum(v * v for v in c_tf.values()))
        return dot / (nq * nc) if nq and nc else 0.0

    # -- search ----------------------------------------------------------
    def search(self, query: str, top_k: int = 5) -> list[dict]:
        q_terms = content_terms(query)
        if not q_terms or not self.chunks:
            return []
        q_tf = Counter(q_terms)
        raw = []
        for chunk in self.chunks:
            bm25 = self._bm25(q_terms, chunk)
            cos = self._cosine(q_tf, chunk.tf)
            raw.append((chunk, bm25, cos))
        max_bm25 = max((r[1] for r in raw), default=0.0) or 1.0
        results = []
        for chunk, bm25, cos in raw:
            hybrid = 0.65 * (bm25 / max_bm25) + 0.35 * cos
            if hybrid <= 0:
                continue
            coverage = (
                sum(1 for t in set(q_terms) if t in chunk.tf) / max(1, len(set(q_terms)))
            )
            results.append({
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "source": chunk.source,
                "heading": chunk.heading,
                "text": chunk.text,
                "score": round(hybrid, 4),
                "bm25": round(bm25, 4),
                "cosine": round(cos, 4),
                "coverage": round(coverage, 4),
            })
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    @staticmethod
    def confidence(results: list[dict]) -> float:
        """Calibrated-ish confidence in [0, 1] from the top hit.

        Blends how completely the top chunk covers the question's terms with
        how strongly it out-scores the field. Out-of-corpus questions get low
        coverage on both axes, which is exactly what drives escalation.
        """
        if not results:
            return 0.0
        top = results[0]
        coverage = top["coverage"]
        strength = min(1.0, top["score"] / 0.75)
        margin = 1.0
        if len(results) > 1 and results[1]["score"] > 0:
            margin = min(1.0, top["score"] / (results[1]["score"] * 1.5))
        return round(0.55 * coverage + 0.35 * strength + 0.10 * margin, 4)
