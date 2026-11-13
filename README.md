# AgentDesk — AI Support Agent with an Evaluation Harness

A self-hosted support agent that answers questions **only from your documents**,
cites its sources on every answer, and **escalates to a human queue whenever its
confidence drops below 0.70**. Ships with a golden-set evaluation harness so every
change is measured, not vibes.

## Measured results (this build, actually run)

Golden set: 34 cases (28 answer + 6 must-escalate) over the bundled sample corpus
(PostgreSQL + vLLM + support-FAQ summaries, 27 chunks), offline extractive mode:

| Metric | Result |
| --- | --- |
| recall@5 | **1.000** |
| correctness (expected terms in answer) | **0.941** |
| grounding (answer sentences verbatim in cited chunks) | **0.982** |
| escalation accuracy (answer/escalate decisions) | **1.000** (34/34) |
| ask latency, in-process | mean 0.27 ms · p95 0.43 ms |

Reproduce with `python -m evals.run_eval` (writes `evals/report.json`).
These numbers are for the small bundled corpus in extractive mode — they are a
baseline to beat with the production wiring below, not a claim about a
3,000-chunk corpus or LLM generation.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./scripts/run.sh            # http://localhost:8000
```

Open the console, click **Load sample docs**, and ask:
- “How does continuous batching work in vLLM?” → cited answer
- “What is a good recipe for sourdough bread?” → escalated, ticket created

Docker: `docker compose up --build` (add `--profile prod` for Postgres+pgvector
and Redis containers).

## How it works

```
question ─► hybrid retrieval ─► confidence ─► ≥ 0.70 ─► answer + citations
 (BM25 + TF-cosine fusion)        │                        │
                                   └─ < 0.70 ─► escalation ticket (human queue)
 repeat question ─► semantic cache (measured hit rate in /stats)
 every step ─► trace spans (GET /traces?trace_id=…)
```

- **Ingestion** — markdown-aware chunking: one chunk per heading section,
  windowed at 512 tokens with 64-token overlap (`app/text.py`).
- **Retrieval** — BM25 + term-vector cosine fused 65/35, with light suffix
  stemming so “connecting” matches “connect” (`app/retrieval.py`).
- **Confidence** — blends top-chunk query coverage, normalised top score, and
  the margin over the runner-up. Out-of-corpus questions score near zero on
  all three, which is what makes the 0.70 gate fire correctly.
- **Answering** — two modes, same contract (answer built only from retrieved
  chunks): *extractive* by default (offline, deterministic, grounded by
  construction; sentences are drawn only from chunks within 50% of the top
  score so one shared word can't leak an unrelated passage in), or *LLM mode*
  against any OpenAI-compatible endpoint.
- **Escalation** — low-confidence questions become tickets with the retrieval
  trace attached; humans resolve them from the console or API.
- **Evals** — `evals/run_eval.py` scores recall@5, correctness, grounding,
  escalation accuracy and latency per case, so a retrieval tweak shows up as a
  number before it ships.

## API

| Endpoint | What it does |
| --- | --- |
| `GET /health`, `GET /stats` | status, counters, cache size |
| `POST /documents` / `POST /documents/upload` | ingest text or a file |
| `POST /ingest/sample` | load the bundled sample corpus |
| `POST /ask` `{question, customer}` | answer with citations, or escalate |
| `GET /escalations`, `POST /escalations/{id}/resolve` | human queue |
| `GET /tickets`, `GET /traces` | all tickets, span log |
| `POST /evals/run` | run the golden set, return measured metrics |

## Turning on LLM mode (vLLM / llama.cpp / OpenAI)

AgentDesk speaks to any OpenAI-compatible `/chat/completions` endpoint:

```bash
# on a GPU host:  vllm serve meta-llama/Llama-3.2-3B-Instruct --port 8001
export LLM_BASE_URL=http://gpu-host:8001/v1
export LLM_MODEL=meta-llama/Llama-3.2-3B-Instruct
./scripts/run.sh     # /health now reports llm_mode: "llm"
```

If the LLM call fails, AgentDesk falls back to extractive answering instead of
erroring. On a Mac (no NVIDIA GPU), develop locally in extractive mode or point
`LLM_BASE_URL` at a llama.cpp server; run measured vLLM serving on a cloud L4
(g6.xlarge, ~$0.80/h, stop the instance when done).

## Production wiring (documented scale-out path)

The default build is deliberately dependency-light (in-process index, optional
JSON state file). The interfaces are shaped so each piece swaps out:

- **Dense retrieval** — replace the TF-cosine side of `HybridIndex.search`
  with sentence-transformers embeddings stored in **Postgres + pgvector**
  (HNSW), keep BM25, add a cross-encoder reranker over the top 20.
- **Cache** — swap the in-process dict for **Redis** keyed by embedding
  similarity (true semantic cache).
- **Async jobs** — long eval sweeps and bulk ingestion go through **Kafka**
  topics instead of the request path; the ask path stays synchronous.
- **Tracing** — spans are already recorded in OpenTelemetry shape (name,
  duration, attributes); install `requirements-optional.txt` and add an OTLP
  exporter to ship them to LangSmith / Phoenix / Jaeger.
- **Storage** — documents, chunks and tickets move to the Postgres schema
  behind the `prod` compose profile.

## Project layout

```
app/        config, text/chunking, hybrid retrieval, llm, agent service, API
frontend/   single-page console (ask, ingest, escalation queue, evals)
data/       sample_docs/ (PostgreSQL, vLLM, FAQ) · golden.jsonl (34 cases)
evals/      run_eval.py — the measurement harness (+ generated report.json)
tests/      14 tests: retrieval, agent behaviour, HTTP API
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q     # 14 passed
```

## What I'd measure next

1. Grow the golden set to 200 cases and the corpus to the full PostgreSQL +
   vLLM docs (~3,000 chunks); re-baseline recall@5 and grounding there.
2. Dense vs hybrid vs hybrid+rerank on the same golden set, with the latency
   cost of each step.
3. LLM mode on vLLM/L4: TTFT/TPOT p50/p99 and cost per 1K tokens, BF16 vs FP8.
