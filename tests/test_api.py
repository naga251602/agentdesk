from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_full_flow_over_http():
    assert client.post("/ingest/sample").status_code == 200

    r = client.post("/ask", json={"question": "What are TTFT and TPOT in LLM serving?"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "answered"
    assert body["citations"][0]["source"] == "vllm.md"

    r = client.post("/ask", json={"question": "Can you book me a flight to Chicago?"})
    assert r.json()["status"] == "escalated"

    esc = client.get("/escalations").json()
    assert len(esc) >= 1
    tid = esc[0]["ticket_id"]
    r = client.post(f"/escalations/{tid}/resolve", json={"resolution": "done"})
    assert r.json()["status"] == "resolved"


def test_evals_endpoint_returns_metrics():
    r = client.post("/evals/run")
    assert r.status_code == 200
    body = r.json()
    assert body["cases"] >= 30
    assert 0.0 <= body["recall_at_5"] <= 1.0
    assert 0.0 <= body["escalation_accuracy"] <= 1.0


def test_ask_rejects_empty_question():
    r = client.post("/ask", json={"question": "   "})
    assert r.status_code == 400
