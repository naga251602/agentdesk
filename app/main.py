"""AgentDesk HTTP API (FastAPI) + static frontend console."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .agent import service
from .config import settings

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "data" / "sample_docs"
GOLDEN = ROOT / "data" / "golden.jsonl"

app = FastAPI(title="AgentDesk", version=__version__)


class AskRequest(BaseModel):
    question: str
    customer: str = "anonymous"


class IngestRequest(BaseModel):
    source: str
    text: str


class ResolveRequest(BaseModel):
    resolution: str


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok", "version": __version__,
        "documents": len(service.documents), "chunks": len(service.index),
        "escalation_threshold": settings.escalation_threshold,
        "llm_mode": "llm" if settings.llm_base_url and settings.llm_model
        else "extractive",
    }


@app.get("/stats")
def stats() -> dict:
    return {**service.stats,
            "documents": len(service.documents), "chunks": len(service.index),
            "open_escalations": len(service.escalations),
            "cache_size": len(service.cache)}


@app.get("/documents")
def documents() -> list[dict]:
    return list(service.documents.values())


@app.post("/documents", status_code=201)
def add_document(req: IngestRequest) -> dict:
    if not req.text.strip():
        raise HTTPException(400, "text is empty")
    return service.ingest(req.source, req.text)


@app.post("/documents/upload", status_code=201)
async def upload_document(file: UploadFile) -> dict:
    raw = await file.read()
    return service.ingest(file.filename or "upload.md",
                          raw.decode("utf-8", errors="replace"))


@app.post("/ingest/sample")
def ingest_sample() -> list[dict]:
    return service.ingest_sample_corpus(SAMPLE_DIR)


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    if not req.question.strip():
        raise HTTPException(400, "question is empty")
    return service.ask(req.question, req.customer)


@app.get("/tickets")
def tickets() -> list[dict]:
    return service.tickets


@app.get("/escalations")
def escalations() -> list[dict]:
    return service.escalations


@app.post("/escalations/{ticket_id}/resolve")
def resolve(ticket_id: str, req: ResolveRequest) -> dict:
    ticket = service.resolve_escalation(ticket_id, req.resolution)
    if ticket is None:
        raise HTTPException(404, "ticket not found")
    return ticket


@app.get("/traces")
def traces(trace_id: str | None = None) -> list[dict]:
    if trace_id:
        return [t for t in service.traces if t["trace_id"] == trace_id]
    return service.traces[-50:]


@app.post("/evals/run")
def run_evals() -> dict:
    from evals.run_eval import evaluate  # local import: evals/ sits beside app/

    if not service.documents:
        service.ingest_sample_corpus(SAMPLE_DIR)
    return evaluate(service, GOLDEN)


@app.get("/")
def home() -> FileResponse:
    return FileResponse(ROOT / "frontend" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
