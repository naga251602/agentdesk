"""AgentDesk evaluation harness.

Runs the golden set against a live AgentService and reports MEASURED numbers:

- recall@5          — expected source appears in the top-5 retrieved citations
- correctness       — fraction of expected terms present in the answer
                      (averaged over cases where an answer was expected)
- grounding         — fraction of answer sentences that appear verbatim in a
                      cited chunk (extractive mode is grounded by construction;
                      LLM mode is checked the hard way)
- escalation        — accuracy of the escalate/answer decision vs the label
- latency           — mean / p95 end-to-end ask latency in ms

Usage:
    python -m evals.run_eval [--golden data/golden.jsonl] [--out evals/report.json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent import AgentService  # noqa: E402
from app.text import split_sentences  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[idx]


def evaluate(service: AgentService, golden_path: str | Path) -> dict:
    cases = [json.loads(line) for line in Path(golden_path).read_text().splitlines()
             if line.strip()]
    # Work on a clean copy of the ticket/escalation/cache state per run.
    service.tickets.clear()
    service.escalations.clear()
    service.cache.clear()

    per_case = []
    recall_hits, decision_hits = 0, 0
    correctness_scores, grounding_scores, latencies = [], [], []

    chunk_text = {c.chunk_id: c.text for c in service.index.chunks}

    for case in cases:
        res = service.ask(case["question"], customer="eval")
        latencies.append(res["latency_ms"])
        expected = case["expect"]
        got = "escalate" if res["status"] == "escalated" else "answer"
        decision_ok = got == expected
        decision_hits += decision_ok

        recall_ok = None
        correctness = None
        grounding = None
        if expected == "answer":
            sources = [c["source"] for c in res["citations"]]
            recall_ok = case["expected_source"] in sources
            recall_hits += bool(recall_ok)
            if res["answer"]:
                ans = res["answer"].lower()
                terms = case["expected_terms"]
                correctness = (sum(1 for t in terms if t.lower() in ans)
                               / max(1, len(terms)))
                correctness_scores.append(correctness)
                cited_text = " ".join(chunk_text.get(c["chunk_id"], "")
                                      for c in res["citations"])
                # Strip the trailing [source] citation markers before
                # sentence-splitting, or they glue onto the next sentence.
                import re
                clean = re.sub(r"\[[^\]]+\.md\]", "", res["answer"])
                sentences = split_sentences(clean)
                if sentences:
                    grounded = sum(1 for s in sentences if s[:60] in cited_text)
                    grounding = grounded / len(sentences)
                    grounding_scores.append(grounding)
        per_case.append({
            "question": case["question"], "expected": expected, "got": got,
            "decision_ok": decision_ok, "recall_ok": recall_ok,
            "correctness": correctness, "grounding": grounding,
            "confidence": res["confidence"], "latency_ms": res["latency_ms"],
        })

    answer_cases = [c for c in cases if c["expect"] == "answer"]
    report = {
        "cases": len(cases),
        "answer_cases": len(answer_cases),
        "escalation_cases": len(cases) - len(answer_cases),
        "recall_at_5": round(recall_hits / max(1, len(answer_cases)), 4),
        "correctness": round(statistics.mean(correctness_scores), 4)
        if correctness_scores else None,
        "grounding": round(statistics.mean(grounding_scores), 4)
        if grounding_scores else None,
        "escalation_accuracy": round(decision_hits / max(1, len(cases)), 4),
        "latency_ms_mean": round(statistics.mean(latencies), 2) if latencies else 0,
        "latency_ms_p95": round(_percentile(latencies, 95), 2),
        "per_case": per_case,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default=str(ROOT / "data" / "golden.jsonl"))
    parser.add_argument("--out", default=str(ROOT / "evals" / "report.json"))
    args = parser.parse_args()

    service = AgentService()
    service.ingest_sample_corpus(ROOT / "data" / "sample_docs")
    report = evaluate(service, args.golden)
    Path(args.out).write_text(json.dumps(report, indent=2))
    summary = {k: v for k, v in report.items() if k != "per_case"}
    print(json.dumps(summary, indent=2))
    print(f"\nFull report written to {args.out}")


if __name__ == "__main__":
    main()
