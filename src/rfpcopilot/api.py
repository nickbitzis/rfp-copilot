"""FastAPI service: upload and process questionnaires, review, export, SME queue, /healthz, /metrics, and the UI."""

from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from . import __version__
from .drafting import Drafter, make_drafter
from .export import compliance_matrix, export_file, matrix_csv
from .kb import build_kb, load_kb
from .logs import event, get_logger, now_ms
from .parser import ParseError
from .pipeline import Pipeline
from .review import ReviewError, Store
from .samples import SAMPLES, sample_bytes

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD = 5 * 1024 * 1024
MEDIA = {"csv": "text/csv", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


class EditBody(BaseModel):
    text: str = Field(max_length=5000)
    compliance: str | None = None
    reviewer: str = Field(default="reviewer", min_length=1, max_length=80)


class ApproveBody(BaseModel):
    reviewer: str = Field(default="reviewer", min_length=1, max_length=80)


class Metrics:
    def __init__(self) -> None:
        r = self.registry = CollectorRegistry()
        self.requests = Counter("rfpcopilot_requests_total", "HTTP requests", ["path", "status"], registry=r)
        self.questions = Counter("rfpcopilot_questions_total", "Question parts processed", ["status"], registry=r)
        self.conflicts = Counter("rfpcopilot_conflicts_total", "Question parts with a source conflict", registry=r)
        self.superseded = Counter("rfpcopilot_superseded_sources_total", "Outdated sources filtered", registry=r)
        self.approvals = Counter("rfpcopilot_approvals_total", "Reviewer approvals", registry=r)
        self.write_backs = Counter("rfpcopilot_library_writebacks_total", "New answers added to the library",
                                   registry=r)
        self.edits = Counter("rfpcopilot_edits_total", "Reviewer edits", registry=r)
        self.process_seconds = Histogram("rfpcopilot_process_seconds", "Time to process one questionnaire",
                                         registry=r, buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30))


def create_app(pipeline: Pipeline | None = None, db_path: str | None = None, drafter: Drafter | None = None) -> FastAPI:
    if pipeline is None:
        kb_dir = os.environ.get("RFPCOPILOT_KB")
        kb = load_kb(Path(kb_dir)) if kb_dir else build_kb()[0]
        pipeline = Pipeline(kb, drafter or make_drafter(os.environ.get("RFPCOPILOT_DRAFTER", "extractive")))
    store = Store(pipeline, db_path or os.environ.get("RFPCOPILOT_DB", ":memory:"))
    metrics, log = Metrics(), get_logger()
    app = FastAPI(title="rfpcopilot", version=__version__)
    app.state.store, app.state.metrics = store, metrics
    known = {"/", "/healthz", "/metrics"}

    @app.middleware("http")
    async def count(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        path = request.url.path
        label = path if path in known else ("/api" if path.startswith("/api") else "other")
        metrics.requests.labels(label, str(response.status_code)).inc()
        if path.startswith("/api"):
            event(log, "request", method=request.method, path=path, status=response.status_code,
                  latency_ms=now_ms(start))
        return response

    def job_or_404(job_id: str) -> dict:
        try:
            return store.get_job(job_id)
        except KeyError:
            raise HTTPException(404, "questionnaire not found") from None

    def ingest(filename: str, content: bytes) -> dict:
        start = time.perf_counter()
        try:
            job = store.create_job(filename, content)
        except (ParseError, ValueError) as exc:
            raise HTTPException(422, f"could not parse questionnaire: {exc}") from None
        metrics.process_seconds.observe(time.perf_counter() - start)
        for it in job["items"]:
            metrics.questions.labels(it["status"]).inc()
            metrics.conflicts.inc(bool(it["conflicts"]))
            metrics.superseded.inc(len(it["superseded"]))
        event(log, "processed", job_id=job["id"], filename=filename, parts=len(job["items"]), counts=job["counts"],
              drafter=pipeline.drafter.name, latency_ms=now_ms(start))
        return job

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (STATIC / "index.html").read_text()

    @app.get("/healthz")
    def healthz() -> dict:
        kb = pipeline.kb
        return {"status": "ok", "version": __version__, "docs": len(kb.docs), "chunks": len(kb.chunks),
                "library_answers": len(kb.library), "drafter": pipeline.drafter.name}

    @app.get("/metrics")
    def prom() -> Response:
        return Response(generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)

    @app.get("/api/samples")
    def samples() -> list[str]:
        return list(SAMPLES)

    @app.post("/api/questionnaires/sample/{name}")
    def load_sample(name: str) -> dict:
        if name not in SAMPLES:
            raise HTTPException(404, "unknown sample")
        return ingest(name, sample_bytes(name))

    @app.post("/api/questionnaires")
    async def upload(file: UploadFile = File(...)) -> dict:
        content = await file.read()
        if len(content) > MAX_UPLOAD:
            raise HTTPException(413, "file is larger than 5 MB")
        name = file.filename or "upload.csv"
        if not name.lower().endswith((".csv", ".xlsx")):
            raise HTTPException(415, "upload a .csv or .xlsx file")
        return ingest(name, content)

    @app.get("/api/questionnaires")
    def list_jobs() -> list[dict]:
        return store.list_jobs()

    @app.get("/api/questionnaires/{job_id}")
    def get_job(job_id: str) -> dict:
        return job_or_404(job_id)

    @app.post("/api/questionnaires/{job_id}/items/{item_id}/edit")
    def edit(job_id: str, item_id: str, body: EditBody) -> dict:
        job_or_404(job_id)
        try:
            it = store.edit(job_id, item_id, body.text, body.compliance, body.reviewer)
        except KeyError:
            raise HTTPException(404, "item not found") from None
        except ReviewError as exc:
            raise HTTPException(422, str(exc)) from None
        metrics.edits.inc()
        event(log, "edit", job_id=job_id, item_id=item_id, reviewer=body.reviewer)
        return it

    @app.post("/api/questionnaires/{job_id}/items/{item_id}/approve")
    def approve(job_id: str, item_id: str, body: ApproveBody) -> dict:
        job_or_404(job_id)
        try:
            it = store.approve(job_id, item_id, body.reviewer)
        except KeyError:
            raise HTTPException(404, "item not found") from None
        except ReviewError as exc:
            raise HTTPException(422, str(exc)) from None
        metrics.approvals.inc()
        if it.get("written_back"):
            metrics.write_backs.inc()
        event(log, "approve", job_id=job_id, item_id=item_id, reviewer=body.reviewer,
              written_back=it.get("written_back"))
        return it

    @app.get("/api/questionnaires/{job_id}/matrix")
    def matrix(job_id: str, format: str = "json", drafts: bool = False):
        job = job_or_404(job_id)
        m = compliance_matrix(job["items"], drafts)
        if format == "csv":
            return Response(matrix_csv(m), media_type="text/csv",
                            headers={"Content-Disposition": f'attachment; filename="{job_id}-matrix.csv"'})
        return JSONResponse(m)

    @app.get("/api/questionnaires/{job_id}/export")
    def export(job_id: str, drafts: bool = False) -> Response:
        job_or_404(job_id)
        filename, fmt, content, layout = store.job_meta(job_id)
        data = export_file(content, fmt, layout, store.items(job_id), drafts)
        stem = filename.rsplit(".", 1)[0]
        return Response(data, media_type=MEDIA[fmt],
                        headers={"Content-Disposition": f'attachment; filename="{stem}-answered.{fmt}"'})

    @app.get("/api/sme-queue")
    def sme_queue() -> list[dict]:
        return store.sme_queue()

    @app.get("/api/library/{answer_id}")
    def library_answer(answer_id: str) -> dict:
        a = pipeline.kb.answer(answer_id)
        if a is None:
            raise HTTPException(404, "answer not found")
        return a.__dict__

    return app


def app_from_env() -> FastAPI:  # pragma: no cover - used by uvicorn --factory
    return create_app()
