import pytest

from rfpcopilot.kb import build_kb
from rfpcopilot.pipeline import Pipeline
from rfpcopilot.review import ReviewError, Store
from rfpcopilot.samples import sample_bytes

NAME = "tallis-freight-security.xlsx"


@pytest.fixture
def store(pipeline):
    return Store(pipeline, clock=lambda: "2026-11-07T10:00:00Z")


def first(job, status):
    return next(i for i in job["items"] if i["status"] == status)


def test_job_counts_and_statuses(store):
    job = store.create_job(NAME, sample_bytes(NAME))
    assert set(job["counts"]) <= {"auto_approved", "needs_review", "sme"}
    assert job["counts"]["sme"] >= 2 and job["counts"]["auto_approved"] >= 5


def test_edit_is_stored_as_a_diff(store):
    job = store.create_job(NAME, sample_bytes(NAME))
    it = first(job, "needs_review")
    out = store.edit(job["id"], it["item_id"], it["draft"]["answer"] + " Reviewed by the security team.", None, "ana")
    diff = out["edits"][0]["diff"]
    assert diff.startswith("--- draft") and "+" in diff and "Reviewed by the security team." in diff
    assert out["edits"][0]["reviewer"] == "ana"


def test_approve_writes_back_with_provenance(store, pipeline):
    job = store.create_job(NAME, sample_bytes(NAME))
    it = first(job, "sme")
    store.edit(job["id"], it["item_id"], "Yes. Corvane carries cyber insurance with a 10 million USD limit.", "yes",
               "legal-counsel")
    out = store.approve(job["id"], it["item_id"], "legal-counsel")
    aid = out["written_back"]
    a = pipeline.kb.answer(aid)
    assert a.status == "approved" and a.approver == "legal-counsel" and a.date == "2026-11-07"
    assert a.provenance["questionnaire"] == NAME and a.provenance["item_id"] == it["item_id"]
    assert a.provenance["edited"] and a.provenance["diffs"]


def test_write_back_closes_the_loop(store, pipeline):
    job = store.create_job(NAME, sample_bytes(NAME))
    it = first(job, "sme")
    store.edit(job["id"], it["item_id"], "Yes. Corvane carries cyber insurance with a 10 million USD limit.", "yes", "r")
    store.approve(job["id"], it["item_id"], "r")
    again = pipeline.answer(it["text"])
    assert again["status"] == "auto_approved" and "10 million" in again["draft"]["answer"]


def test_approving_exact_match_does_not_duplicate_library(store, pipeline):
    job = store.create_job(NAME, sample_bytes(NAME))
    n = len(pipeline.kb.library)
    it = first(job, "auto_approved")
    store.approve(job["id"], it["item_id"], "r")
    assert len(pipeline.kb.library) == n


def test_cannot_approve_empty_answer(store):
    job = store.create_job(NAME, sample_bytes(NAME))
    with pytest.raises(ReviewError):
        store.approve(job["id"], first(job, "sme")["item_id"], "r")


def test_library_additions_survive_restart(tmp_path):
    db = str(tmp_path / "rfp.db")
    s1 = Store(Pipeline(build_kb()[0]), db)
    job = s1.create_job(NAME, sample_bytes(NAME))
    it = first(job, "sme")
    s1.edit(job["id"], it["item_id"], "No. Corvane does not hold that certification.", "no", "r")
    aid = s1.approve(job["id"], it["item_id"], "r")["written_back"]
    s2 = Store(Pipeline(build_kb()[0]), db)
    assert s2.pipeline.kb.answer(aid) is not None
    assert s2.sme_queue() and all(q["item_id"] != it["item_id"] for q in s2.sme_queue())
