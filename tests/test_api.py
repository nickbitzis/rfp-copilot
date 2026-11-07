import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from rfpcopilot.api import create_app

SAMPLE = "tallis-freight-security.xlsx"


@pytest.fixture
def client(pipeline):
    return TestClient(create_app(pipeline))


def test_healthz_and_index(client):
    h = client.get("/healthz").json()
    assert h["status"] == "ok" and h["docs"] == 60 and h["drafter"] == "extractive"
    assert "RFP Copilot" in client.get("/").text


def test_end_to_end_review_and_export(client):
    job = client.post(f"/api/questionnaires/sample/{SAMPLE}").json()
    jid = job["id"]
    it = next(i for i in job["items"] if i["status"] == "needs_review")
    r = client.post(f"/api/questionnaires/{jid}/items/{it['item_id']}/edit",
                    json={"text": it["draft"]["answer"], "compliance": "yes", "reviewer": "ana"})
    assert r.status_code == 200 and r.json()["edits"]
    r = client.post(f"/api/questionnaires/{jid}/items/{it['item_id']}/approve", json={"reviewer": "ana"})
    assert r.json()["status"] == "approved" and r.json()["written_back"].startswith("A-")
    lib = client.get(f"/api/library/{r.json()['written_back']}").json()
    assert lib["provenance"]["job_id"] == jid
    out = client.get(f"/api/questionnaires/{jid}/export")
    assert out.status_code == 200 and "answered.xlsx" in out.headers["content-disposition"]
    ws = load_workbook(io.BytesIO(out.content))["Security Questionnaire"]
    assert ws.cell(it["row"] + 1, 4).value
    m = client.get(f"/api/questionnaires/{jid}/matrix").json()
    assert m["status"]["approved"] == 1
    assert client.get(f"/api/questionnaires/{jid}/matrix?format=csv").text.startswith("Section,")


def test_upload_xlsx(client):
    wb = Workbook()
    ws = wb.active
    ws.append(["Question", "Response"])
    ws.append(["Do you support SSO?", None])
    ws.append(["Do you hold FedRAMP Moderate authorization?", None])
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post("/api/questionnaires", files={"file": ("mine.xlsx", buf.getvalue(), "application/octet-stream")})
    assert r.status_code == 200
    statuses = [i["status"] for i in r.json()["items"]]
    assert statuses == ["auto_approved", "sme"]


def test_upload_rejects_bad_files(client):
    assert client.post("/api/questionnaires", files={"file": ("a.pdf", b"%PDF", "application/pdf")}).status_code == 415
    r = client.post("/api/questionnaires", files={"file": ("a.csv", b"just,one,row\n", "text/csv")})
    assert r.status_code == 422


def test_not_found(client):
    assert client.get("/api/questionnaires/nope").status_code == 404
    assert client.post("/api/questionnaires/sample/nope.csv").status_code == 404
    jid = client.post(f"/api/questionnaires/sample/{SAMPLE}").json()["id"]
    assert client.post(f"/api/questionnaires/{jid}/items/r999/approve", json={}).status_code == 404


def test_approve_empty_is_422(client):
    job = client.post(f"/api/questionnaires/sample/{SAMPLE}").json()
    sme = next(i for i in job["items"] if i["status"] == "sme")
    r = client.post(f"/api/questionnaires/{job['id']}/items/{sme['item_id']}/approve", json={"reviewer": "x"})
    assert r.status_code == 422


def test_sme_queue_and_list(client):
    client.post("/api/questionnaires/sample/merrow-health-rfp.csv")
    q = client.get("/api/sme-queue").json()
    assert q and all(x["team"] for x in q)
    assert len(client.get("/api/questionnaires").json()) == 1


def test_metrics_endpoint(client):
    client.post(f"/api/questionnaires/sample/{SAMPLE}")
    text = client.get("/metrics").text
    assert 'rfpcopilot_questions_total{status="auto_approved"}' in text
    assert "rfpcopilot_process_seconds_bucket" in text
