"""Knowledge base: policy and product docs (chunked by heading) plus the approved answer library.

`build_kb()` generates the synthetic Corvane corpus deterministically from kbdata.py. `save_kb()` writes it to
disk as markdown and JSON, and `load_kb()` reads it back, so a real team could swap in its own files.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .kbdata import APPROVERS, DOC_TITLES, EXTRA_DOCS, SUBPROCESSORS, TOPICS

CURRENT_VERSION = "6.2"
SEED = 7


@dataclass
class Doc:
    id: str
    title: str
    section: str
    effective: str
    version: str
    body: str  # markdown


@dataclass
class Chunk:
    id: str  # "<doc id>#<n>"
    doc_id: str
    title: str
    heading: str
    text: str
    effective: str


@dataclass
class LibraryAnswer:
    id: str
    question: str
    answer: str
    compliance: str
    approver: str
    date: str
    product_version: str
    tags: list[str]
    status: str = "approved"  # approved | draft
    provenance: dict = field(default_factory=dict)


@dataclass
class KnowledgeBase:
    docs: list[Doc]
    chunks: list[Chunk]
    library: list[LibraryAnswer]

    def source_text(self, source_id: str) -> str:
        for c in self.chunks:
            if c.id == source_id:
                return c.text
        for a in self.library:
            if a.id == source_id:
                return f"{a.question}\n{a.answer}"
        return ""

    def answer(self, answer_id: str) -> LibraryAnswer | None:
        return next((a for a in self.library if a.id == answer_id), None)

    def chunk(self, chunk_id: str) -> Chunk | None:
        return next((c for c in self.chunks if c.id == chunk_id), None)

    def next_answer_id(self) -> str:
        n = max((int(a.id.split("-")[1]) for a in self.library), default=0)
        return f"A-{n + 1:04d}"


# ---- chunking ---------------------------------------------------------------------------------

def chunk_doc(doc: Doc) -> list[Chunk]:
    """One chunk per '## ' section. The doc title is prepended so each chunk stands alone for BM25."""
    parts = re.split(r"^## ", doc.body, flags=re.M)
    chunks = []
    for part in parts[1:]:
        heading, _, text = part.partition("\n")
        text = text.strip()
        if not text:
            continue
        cid = f"{doc.id}#{len(chunks)}"
        chunks.append(Chunk(cid, doc.id, doc.title, heading.strip(), f"{doc.title}: {heading.strip()}. {text}",
                            doc.effective))
    return chunks


def _strip_polarity(answer: str) -> str:
    return re.sub(r"^(Yes|No|Partial)\.\s*", "", answer)


def _heading(key: str) -> str:
    return key.replace("-", " ").capitalize()


# ---- generation -------------------------------------------------------------------------------

def _effective(rng: random.Random) -> str:
    return (date(2026, 1, 5) + timedelta(days=rng.randint(0, 240))).isoformat()


def _version_for(d: str) -> str:
    y = int(d[:4])
    return {2022: "4.1", 2023: "4.6", 2024: "5.3", 2025: "6.0"}.get(y, CURRENT_VERSION)


def build_docs(rng: random.Random) -> list[Doc]:
    by_doc: dict[str, list] = {}
    for t in TOPICS:
        by_doc.setdefault(t.doc, []).append(t)
    docs: list[Doc] = []
    for doc_id, topics in by_doc.items():
        title = DOC_TITLES[doc_id]
        lines = [f"# {title}", "", "## Purpose",
                 "This document sets the rules described below. It applies to all employees, contractors, and "
                 "production systems.", ""]
        for t in topics:
            lines += [f"## {_heading(t.key)}", _strip_polarity(t.answer), ""]
        if doc_id == "legal-subprocessors":
            lines += ["## Current subprocessors", "| Subprocessor | Purpose | Location |", "|---|---|---|"]
            lines += [f"| {a} | {b} | {c} |" for a, b, c in SUBPROCESSORS] + [""]
        lines += ["## Ownership and review",
                  "The owner of this document is the security-lead. It is reviewed at least once a year and after "
                  "any major change to the platform.", ""]
        eff = _effective(rng)
        docs.append(Doc(doc_id, title, topics[0].section, eff, f"{rng.randint(2, 6)}.{rng.randint(0, 4)}",
                        "\n".join(lines)))
    for doc_id, (title, section, text) in EXTRA_DOCS.items():
        body = f"# {title}\n\n## Scope\nThis document applies to Corvane staff and systems.\n\n## Requirements\n{text}\n"
        docs.append(Doc(doc_id, title, section, _effective(rng), f"{rng.randint(1, 4)}.{rng.randint(0, 4)}", body))
    return docs


def build_library(rng: random.Random) -> tuple[list[LibraryAnswer], dict]:
    """Returns the library and the hidden ground truth (which ids are current, outdated, contradictory)."""
    lib: list[LibraryAnswer] = []
    truth = {"current": {}, "outdated": [], "contradictory": [], "topic_of": {}}

    def add(topic, question, answer, d, status="approved"):
        aid = f"A-{len(lib) + 1:04d}"
        lib.append(LibraryAnswer(aid, question, answer, topic.compliance if answer == topic.answer else
                                 answer.split(".")[0].lower(), rng.choice(APPROVERS), d, _version_for(d),
                                 list(topic.tags), status))
        truth["topic_of"][aid] = topic.key
        return aid

    start = date(2024, 9, 1)
    for t in TOPICS:
        n = 4 if rng.random() < 0.55 else 3
        dates = sorted(start + timedelta(days=rng.randint(0, 770)) for _ in range(n))
        ids = []
        for i in range(n):
            status = "draft" if (i == 0 and rng.random() < 0.08) else "approved"
            ids.append(add(t, t.library_questions[i % len(t.library_questions)], t.answer, dates[i].isoformat(), status))
        truth["current"][t.key] = ids
        if t.old_answer:
            old = date.fromisoformat(t.old_date)
            for j in range(1 if rng.random() < 0.5 else 2):
                d = (old + timedelta(days=21 * j)).isoformat()
                truth["outdated"].append(add(t, t.library_questions[j], t.old_answer, d))
        if t.contra_answer:
            d = (dates[-1] - timedelta(days=30)).isoformat()
            truth["contradictory"].append(add(t, t.library_questions[0], t.contra_answer, d))
    # Shuffle so ids do not reveal age.
    order = list(range(len(lib)))
    rng.shuffle(order)
    remap = {lib[i].id: f"A-{k + 1:04d}" for k, i in enumerate(order)}
    lib = [lib[i] for i in order]
    for a in lib:
        a.id = remap[a.id]
    truth["current"] = {k: [remap[i] for i in v] for k, v in truth["current"].items()}
    truth["outdated"] = sorted(remap[i] for i in truth["outdated"])
    truth["contradictory"] = sorted(remap[i] for i in truth["contradictory"])
    truth["topic_of"] = {remap[k]: v for k, v in truth["topic_of"].items()}
    lib.sort(key=lambda a: a.id)
    return lib, truth


def build_kb(seed: int = SEED) -> tuple[KnowledgeBase, dict]:
    rng = random.Random(seed)
    docs = build_docs(rng)
    lib, truth = build_library(rng)
    chunks = [c for d in docs for c in chunk_doc(d)]
    truth["doc_chunk"] = {}
    for t in TOPICS:
        for c in chunks:
            if c.doc_id == t.doc and c.heading == _heading(t.key):
                truth["doc_chunk"][t.key] = c.id
    return KnowledgeBase(docs, chunks, lib), truth


# ---- persistence ------------------------------------------------------------------------------

def save_kb(kb: KnowledgeBase, root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    for d in kb.docs:
        front = f"---\nid: {d.id}\ntitle: {d.title}\nsection: {d.section}\nversion: {d.version}\neffective: {d.effective}\n---\n"
        (root / "docs" / f"{d.id}.md").write_text(front + d.body)
    (root / "answers.json").write_text(json.dumps([asdict(a) for a in kb.library], indent=1) + "\n")


def load_kb(root: Path) -> KnowledgeBase:
    docs = []
    for p in sorted((root / "docs").glob("*.md")):
        raw = p.read_text()
        _, front, body = raw.split("---\n", 2)
        meta = dict(line.split(": ", 1) for line in front.strip().splitlines())
        docs.append(Doc(meta["id"], meta["title"], meta["section"], meta["effective"], meta["version"], body))
    library = [LibraryAnswer(**a) for a in json.loads((root / "answers.json").read_text())]
    return KnowledgeBase(docs, [c for d in docs for c in chunk_doc(d)], library)
