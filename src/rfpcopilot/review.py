"""Review workflow and persistence (SQLite).

- A job is one uploaded questionnaire: the original bytes, the detected layout, and one item per question part.
- Reviewer edits are stored as unified diffs against the previous text, with who and when.
- Approving an item that is not a verbatim library answer writes a new approved answer back to the library,
  with provenance (questionnaire, item, reviewer, the sources it was based on, and the diff). The retriever is
  rebuilt, so the next questionnaire that asks the same thing gets an exact match.
"""

from __future__ import annotations

import difflib
import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime

from .drafting import validate
from .kb import CURRENT_VERSION, LibraryAnswer
from .parser import ParsedQuestionnaire, parse_file
from .pipeline import Pipeline
from .text import find_citations, strip_citations

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, filename TEXT, fmt TEXT, created_at TEXT, content BLOB,
                                 layout TEXT);
CREATE TABLE IF NOT EXISTS items (job_id TEXT, item_id TEXT, position INTEGER, data TEXT,
                                  PRIMARY KEY (job_id, item_id));
CREATE TABLE IF NOT EXISTS edits (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, item_id TEXT, reviewer TEXT,
                                  ts TEXT, diff TEXT);
CREATE TABLE IF NOT EXISTS library_additions (id TEXT PRIMARY KEY, data TEXT);
"""


class ReviewError(ValueError):
    pass


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_diff(before: str, after: str) -> str:
    return "".join(difflib.unified_diff(before.splitlines(keepends=True) or [""],
                                        after.splitlines(keepends=True) or [""], "draft", "edited", n=0))


class Store:
    def __init__(self, pipeline: Pipeline, path: str = ":memory:", clock=now):
        self.pipeline, self.clock = pipeline, clock
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript(SCHEMA)
        self.lock = threading.Lock()
        self._load_additions()

    def _load_additions(self) -> None:
        rows = self.db.execute("SELECT data FROM library_additions ORDER BY id").fetchall()
        known = {a.id for a in self.pipeline.kb.library}
        for (data,) in rows:
            a = LibraryAnswer(**json.loads(data))
            if a.id not in known:
                self.pipeline.kb.library.append(a)
        if rows:
            self.pipeline.refresh()

    # -- jobs ---------------------------------------------------------------------------------

    def create_job(self, filename: str, content: bytes) -> dict:
        parsed: ParsedQuestionnaire = parse_file(content, filename)
        items = self.pipeline.process(parsed)
        job_id = uuid.uuid4().hex[:12]
        with self.lock:
            self.db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?)",
                            (job_id, filename, parsed.layout.fmt, self.clock(), content,
                             json.dumps(parsed.layout.to_dict())))
            self.db.executemany("INSERT INTO items VALUES (?,?,?,?)",
                                [(job_id, it["item_id"], i, json.dumps(it)) for i, it in enumerate(items)])
            self.db.commit()
        return self.get_job(job_id)

    def list_jobs(self) -> list[dict]:
        rows = self.db.execute("SELECT id, filename, fmt, created_at FROM jobs ORDER BY created_at DESC").fetchall()
        return [{"id": r[0], "filename": r[1], "fmt": r[2], "created_at": r[3]} for r in rows]

    def job_meta(self, job_id: str) -> tuple[str, str, bytes, dict]:
        row = self.db.execute("SELECT filename, fmt, content, layout FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return row[0], row[1], row[2], json.loads(row[3])

    def items(self, job_id: str) -> list[dict]:
        rows = self.db.execute("SELECT data FROM items WHERE job_id=? ORDER BY position", (job_id,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def get_job(self, job_id: str) -> dict:
        filename, fmt, _, layout = self.job_meta(job_id)
        items = self.items(job_id)
        counts: dict[str, int] = {}
        for it in items:
            counts[it["status"]] = counts.get(it["status"], 0) + 1
        return {"id": job_id, "filename": filename, "fmt": fmt, "layout": layout, "counts": counts, "items": items}

    def item(self, job_id: str, item_id: str) -> dict:
        row = self.db.execute("SELECT data FROM items WHERE job_id=? AND item_id=?", (job_id, item_id)).fetchone()
        if row is None:
            raise KeyError(item_id)
        return json.loads(row[0])

    def _save(self, job_id: str, it: dict) -> None:
        self.db.execute("UPDATE items SET data=? WHERE job_id=? AND item_id=?", (json.dumps(it), job_id, it["item_id"]))
        self.db.commit()

    # -- review -------------------------------------------------------------------------------

    def edit(self, job_id: str, item_id: str, text: str, compliance: str | None, reviewer: str) -> dict:
        with self.lock:
            it = self.item(job_id, item_id)
            before = it["final_answer"] or it["draft"]["answer"]
            diff = make_diff(before, text)
            it["final_answer"] = text
            if compliance:
                if compliance not in ("yes", "no", "partial", "unanswered"):
                    raise ReviewError(f"bad compliance {compliance!r}")
                it["final_compliance"] = compliance
            it["edits"].append({"reviewer": reviewer, "ts": self.clock(), "diff": diff})
            if it["status"] in ("auto_approved", "approved"):
                it["status"] = "needs_review"
                it["approved_by"] = ""
            elif it["status"] == "sme":
                it["status"] = "needs_review"
            self.db.execute("INSERT INTO edits (job_id, item_id, reviewer, ts, diff) VALUES (?,?,?,?,?)",
                            (job_id, item_id, reviewer, self.clock(), diff))
            self._save(job_id, it)
            return it

    def approve(self, job_id: str, item_id: str, reviewer: str) -> dict:
        with self.lock:
            it = self.item(job_id, item_id)
            text = it["final_answer"] or it["draft"]["answer"]
            compliance = it["final_compliance"] or it["draft"]["compliance"]
            if not text.strip() or compliance == "unanswered":
                raise ReviewError("nothing to approve: write an answer first")
            edited = bool(it["edits"])
            if not edited:
                # Unedited drafts must still pass the citation validator.
                sources = {s["id"]: f"{s['question']} {s['text']}" for s in it["sources"]}
                from .drafting import Draft

                v = validate(Draft(text, compliance, find_citations(text), 1.0), sources)
                if not v.ok:
                    raise ReviewError("draft fails validation: " + "; ".join(v.errors))
            it.update(final_answer=text, final_compliance=compliance, status="approved", approved_by=reviewer)
            exact = it["draft"].get("exact_match")
            if edited or not exact:
                it["written_back"] = self._write_back(job_id, it, text, compliance, reviewer)
            self._save(job_id, it)
            return it

    def _write_back(self, job_id: str, it: dict, text: str, compliance: str, reviewer: str) -> str:
        kb = self.pipeline.kb
        filename = self.job_meta(job_id)[0]
        aid = kb.next_answer_id()
        answer = LibraryAnswer(
            id=aid, question=it["text"], answer=strip_citations(text), compliance=compliance, approver=reviewer,
            date=self.clock()[:10], product_version=CURRENT_VERSION,
            tags=[it.get("section", "").lower().replace(" ", "-")] if it.get("section") else [],
            status="approved",
            provenance={"questionnaire": filename, "job_id": job_id, "item_id": it["item_id"],
                        "based_on": find_citations(text) or it["draft"]["citations"],
                        "edited": bool(it["edits"]), "diffs": [e["diff"] for e in it["edits"]],
                        "approved_at": self.clock()},
        )
        kb.library.append(answer)
        self.db.execute("INSERT INTO library_additions VALUES (?,?)", (aid, json.dumps(answer.__dict__)))
        self.pipeline.refresh()
        return aid

    def sme_queue(self) -> list[dict]:
        out = []
        for job in self.list_jobs():
            for it in self.items(job["id"]):
                if it["status"] == "sme":
                    out.append({"job_id": job["id"], "filename": job["filename"], "item_id": it["item_id"],
                                "question": it["text"], "section": it["section"], "team": it["sme_team"],
                                "reason": it["draft"]["needs_review"]})
        return out
