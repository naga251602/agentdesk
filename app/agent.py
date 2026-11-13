"""AgentDesk service: ingestion, ask pipeline, escalation queue, cache, traces.

Pipeline for every question:
  retrieve (hybrid) -> confidence -> [>= threshold] answer with citations
                                  -> [<  threshold] escalate to a human queue
Repeat questions are served from a semantic cache (normalised-question match).
Every step records a span in an in-process trace log (OpenTelemetry-shaped:
name, duration_ms, attributes) so any answer can be explained after the fact.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

from .config import settings
from .llm import generate_answer
from .retrieval import Chunk, HybridIndex
from .text import chunk_document


class AgentService:
    def __init__(self) -> None:
        self.index = HybridIndex()
        self.documents: dict[str, dict] = {}
        self.tickets: list[dict] = []
        self.escalations: list[dict] = []
        self.cache: dict[str, dict] = {}
        self.traces: list[dict] = []
        self.stats = {"asked": 0, "answered": 0, "escalated": 0, "cache_hits": 0}
        if settings.state_file:
            self._load()

    # -- persistence (optional, JSON) ------------------------------------
    def _persist(self) -> None:
        if not settings.state_file:
            return
        data = {
            "documents": self.documents,
            "chunks": [
                {"chunk_id": c.chunk_id, "doc_id": c.doc_id, "source": c.source,
                 "heading": c.heading, "text": c.text}
                for c in self.index.chunks
            ],
            "tickets": self.tickets,
            "escalations": self.escalations,
        }
        path = Path(settings.state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def _load(self) -> None:
        path = Path(settings.state_file)
        if not path.exists():
            return
        data = json.loads(path.read_text())
        self.documents = data.get("documents", {})
        self.tickets = data.get("tickets", [])
        self.escalations = data.get("escalations", [])
        for c in data.get("chunks", []):
            self.index.add(Chunk(c["chunk_id"], c["doc_id"], c["source"],
                                 c["heading"], c["text"]))

    # -- tracing ----------------------------------------------------------
    def _span(self, trace_id: str, name: str, started: float, **attrs) -> None:
        self.traces.append({
            "trace_id": trace_id, "span": name,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "attributes": attrs,
        })
        self.traces = self.traces[-500:]  # keep the log bounded

    # -- ingestion ---------------------------------------------------------
    def ingest(self, source: str, text: str) -> dict:
        doc_id = hashlib.sha1(source.encode()).hexdigest()[:10]
        pieces = chunk_document(text, settings.chunk_tokens, settings.chunk_overlap)
        for i, piece in enumerate(pieces):
            self.index.add(Chunk(f"{doc_id}-{i}", doc_id, source,
                                 piece["heading"], piece["text"]))
        self.documents[doc_id] = {"doc_id": doc_id, "source": source,
                                  "chunks": len(pieces)}
        self.cache.clear()  # corpus changed; cached answers may be stale
        self._persist()
        return self.documents[doc_id]

    def ingest_sample_corpus(self, data_dir: str | Path) -> list[dict]:
        out = []
        for path in sorted(Path(data_dir).glob("*.md")):
            out.append(self.ingest(path.name, path.read_text()))
        return out

    # -- ask ---------------------------------------------------------------
    @staticmethod
    def _cache_key(question: str) -> str:
        return " ".join(question.lower().split()).strip("?.")

    def ask(self, question: str, customer: str = "anonymous") -> dict:
        trace_id = uuid.uuid4().hex[:12]
        t0 = time.perf_counter()
        self.stats["asked"] += 1

        key = self._cache_key(question)
        if key in self.cache:
            self.stats["cache_hits"] += 1
            hit = dict(self.cache[key])
            hit["cached"] = True
            hit["trace_id"] = trace_id
            self._span(trace_id, "cache.hit", t0)
            return hit

        t = time.perf_counter()
        results = self.index.search(question, settings.top_k)
        self._span(trace_id, "retrieval.hybrid", t, hits=len(results))
        confidence = self.index.confidence(results)

        citations = [
            {"source": r["source"], "heading": r["heading"],
             "chunk_id": r["chunk_id"], "score": r["score"]}
            for r in results[:3]
        ]

        if confidence < settings.escalation_threshold or not results:
            ticket = {
                "ticket_id": f"T-{len(self.tickets) + 1:04d}",
                "question": question, "customer": customer,
                "confidence": confidence, "status": "open",
                "reason": "low_confidence", "trace_id": trace_id,
                "top_candidates": citations,
            }
            self.tickets.append(ticket)
            self.escalations.append(ticket)
            self.stats["escalated"] += 1
            self._span(trace_id, "escalation.create", t0,
                       ticket=ticket["ticket_id"])
            self._persist()
            return {
                "status": "escalated", "answer": None,
                "confidence": confidence, "citations": citations,
                "ticket": ticket, "cached": False, "trace_id": trace_id,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            }

        t = time.perf_counter()
        answer, mode = generate_answer(question, results)
        self._span(trace_id, "generation", t, mode=mode)
        self.stats["answered"] += 1
        response = {
            "status": "answered", "answer": answer, "mode": mode,
            "confidence": confidence, "citations": citations,
            "ticket": None, "cached": False, "trace_id": trace_id,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        }
        self.cache[key] = response
        self._persist()
        return response

    # -- human queue ---------------------------------------------------------
    def resolve_escalation(self, ticket_id: str, resolution: str) -> dict | None:
        for ticket in self.tickets:
            if ticket["ticket_id"] == ticket_id:
                ticket["status"] = "resolved"
                ticket["resolution"] = resolution
                self.escalations = [e for e in self.escalations
                                    if e["ticket_id"] != ticket_id]
                self._persist()
                return ticket
        return None


service = AgentService()
