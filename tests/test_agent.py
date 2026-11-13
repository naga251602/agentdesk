from pathlib import Path

from app.agent import AgentService

ROOT = Path(__file__).resolve().parent.parent


def loaded_service() -> AgentService:
    svc = AgentService()
    svc.ingest_sample_corpus(ROOT / "data" / "sample_docs")
    return svc


def test_ingest_sample_corpus():
    svc = loaded_service()
    assert len(svc.documents) == 3
    assert len(svc.index) >= 20  # heading sections across the 3 docs


def test_ask_in_corpus_answers_with_citations():
    svc = loaded_service()
    res = svc.ask("How does continuous batching work in vLLM?")
    assert res["status"] == "answered"
    assert res["confidence"] >= 0.70
    assert res["citations"]
    assert res["citations"][0]["source"] == "vllm.md"
    assert res["answer"]


def test_ask_out_of_corpus_escalates():
    svc = loaded_service()
    res = svc.ask("What is a good recipe for sourdough bread?")
    assert res["status"] == "escalated"
    assert res["ticket"]["status"] == "open"
    assert svc.escalations and svc.escalations[0]["ticket_id"] == res["ticket"]["ticket_id"]


def test_repeat_question_is_cached():
    svc = loaded_service()
    first = svc.ask("What is PagedAttention in vLLM?")
    second = svc.ask("What is PagedAttention in vLLM?")
    assert first["cached"] is False
    assert second["cached"] is True
    assert svc.stats["cache_hits"] == 1


def test_resolve_escalation_closes_ticket():
    svc = loaded_service()
    res = svc.ask("How do I renew my driving licence?")
    ticket = svc.resolve_escalation(res["ticket"]["ticket_id"], "Called the user")
    assert ticket["status"] == "resolved"
    assert svc.escalations == []
