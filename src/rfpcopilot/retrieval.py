"""Candidate retrieval with recency rules and conflict detection.

Two modes, compared in the eval:
- "bm25": one BM25 index over library answers and doc chunks. No recency or approval rules.
- "hybrid": BM25 over the library blended with fuzzy question similarity, BM25 over doc chunks, and then the
  recency rules: drafts rank below approved answers, an answer that disagrees with a newer answer (by more than
  180 days) or with a newer policy doc is marked superseded and dropped, and disagreements that recency cannot
  settle are raised as conflicts for a reviewer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from .kb import KnowledgeBase
from .text import BM25, extract_facts, facts_conflict, question_similarity, sentences, tokenize

SUPERSEDE_GAP_DAYS = 180


@dataclass
class Candidate:
    id: str
    kind: str  # answer | doc
    text: str
    score: float
    bm25: float = 0.0
    qsim: float = 0.0
    date: str = ""
    status: str = "approved"
    question: str = ""
    title: str = ""
    compliance: str = ""

    def public(self) -> dict:
        return {"id": self.id, "kind": self.kind, "text": self.text, "score": round(self.score, 3),
                "qsim": round(self.qsim, 3), "date": self.date, "status": self.status, "question": self.question,
                "title": self.title}


@dataclass
class Retrieval:
    candidates: list[Candidate]
    superseded: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    coverage: float = 0.0


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days


def best_sentence_facts(answer_text: str, chunk_text: str) -> dict:
    """Facts of the doc sentence that best matches the answer, so unrelated numbers in the chunk are ignored."""
    at = set(tokenize(answer_text))
    best = max(sentences(chunk_text), key=lambda s: len(at & set(tokenize(s))), default="")
    if not at or len(at & set(tokenize(best))) / len(at) < 0.4:
        return {}  # the doc does not state this fact, so there is nothing to compare
    return extract_facts(best)


def _restates(answer: str, chunk: str) -> bool:
    at = set(tokenize(answer))
    return bool(at) and len(at & set(tokenize(chunk))) / len(at) >= 0.7


def same_subject(a: Candidate, b: Candidate) -> bool:
    """Two library answers are about the same thing when their questions match or their answers mostly overlap.
    Answers to different questions can disagree on polarity without contradicting each other."""
    if question_similarity(a.question, b.question) >= 0.75:
        return True
    ta, tb = set(tokenize(a.text)), set(tokenize(b.text))
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= 0.45


class Retriever:
    def __init__(self, kb: KnowledgeBase, mode: str = "hybrid"):
        if mode not in ("bm25", "hybrid"):
            raise ValueError(f"unknown retrieval mode {mode!r}")
        self.kb, self.mode = kb, mode
        self.rebuild()

    def rebuild(self) -> None:
        kb = self.kb
        self.answer_tokens = [tokenize(f"{a.question} {a.answer}") for a in kb.library]
        self.chunk_tokens = [tokenize(c.text) for c in kb.chunks]
        self.answer_index = BM25(self.answer_tokens)
        self.chunk_index = BM25(self.chunk_tokens)
        self.joint_index = BM25(self.answer_tokens + self.chunk_tokens)
        self.idf = self.joint_index.idf
        self.vocab = set(self.idf)

    def unknown_terms(self, query: str) -> list[str]:
        """Acronyms and product-style names (FedRAMP, CMMC) that appear nowhere in the knowledge base.
        A question about a named standard we never mention is not something to answer by analogy."""
        found = re.findall(r"\b[A-Z][A-Za-z]*[A-Z][A-Za-z]*\b", query)
        return [w for w in found if (toks := tokenize(w)) and not any(t in self.vocab for t in toks)]

    # -- scoring ---------------------------------------------------------------------------------

    def coverage(self, query: str, cand_text: str) -> float:
        """IDF-weighted share of the query's terms found in a candidate. Low coverage means the knowledge
        base does not talk about what was asked, which is the abstention signal."""
        q = set(tokenize(query))
        if not q:
            return 0.0
        found = set(tokenize(cand_text))
        weight = {t: self.idf.get(t, 7.0) for t in q}  # unseen terms are rare, so weigh them heavily
        return sum(w for t, w in weight.items() if t in found) / sum(weight.values())

    def _answer_candidate(self, i: int, bm: float, qsim: float, score: float) -> Candidate:
        a = self.kb.library[i]
        return Candidate(a.id, "answer", a.answer, score, bm, qsim, a.date, a.status, a.question,
                         compliance=a.compliance)

    def _chunk_candidate(self, i: int, bm: float, score: float) -> Candidate:
        c = self.kb.chunks[i]
        return Candidate(c.id, "doc", c.text, score, bm, 0.0, c.effective, "approved", title=c.title)

    def retrieve(self, query: str, k: int = 5, context: str = "") -> Retrieval:
        q = tokenize(f"{context} {query}" if context else query)
        if self.mode == "bm25":
            return self._bm25(q, query, k)
        return self._hybrid(q, query, k, context)

    def _bm25(self, q: list[str], query: str, k: int) -> Retrieval:
        scores = self.joint_index.scores(q)
        n_ans = len(self.kb.library)
        top = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        out = []
        for i in top:
            if scores[i] <= 0:
                continue
            if i < n_ans:
                out.append(self._answer_candidate(i, scores[i], 0.0, scores[i]))
            else:
                out.append(self._chunk_candidate(i - n_ans, scores[i], scores[i]))
        cov = self.coverage(query, " ".join(f"{c.question} {c.text}" for c in out[:3]))
        if self.unknown_terms(query):
            cov = 0.0
        return Retrieval(out, coverage=cov)

    def _hybrid(self, q: list[str], query: str, k: int, context: str) -> Retrieval:
        kb = self.kb
        a_bm = self.answer_index.scores(q)
        a_max = max(a_bm) or 1.0
        answers = []
        for i, s in enumerate(a_bm):
            if s <= 0:
                continue
            qsim = question_similarity(query, kb.library[i].question)
            if context:
                qsim = max(qsim, question_similarity(f"{context} {query}", kb.library[i].question) - 0.05)
            score = 0.5 * (s / a_max) + 0.5 * qsim
            if kb.library[i].status != "approved":
                score *= 0.8
            answers.append(self._answer_candidate(i, s, qsim, score))
        # Recency as a tie breaker among near-equal answers: up to +0.03 for the newest.
        for c in answers:
            c.score += 0.03 * max(0.0, 1 - _days("2026-12-31", c.date) / 1500)
        c_bm = self.chunk_index.scores(q)
        c_max = max(c_bm) or 1.0
        chunks = sorted((self._chunk_candidate(i, s, 0.9 * s / c_max) for i, s in enumerate(c_bm) if s > 0),
                        key=lambda c: -c.score)[:4]
        # Agreement between sources: an answer that restates one of the top policy chunks gets a boost.
        for c in answers:
            if any(_restates(c.text, ch.text) for ch in chunks[:2]):
                c.score += 0.1
        answers.sort(key=lambda c: -c.score)
        answers = answers[: max(k * 3, 12)]

        superseded, conflicts = self._apply_recency(answers, chunks)
        kept = [c for c in answers if c.id not in {s["id"] for s in superseded}]
        merged = sorted(kept[: k - 1] + chunks[:2], key=lambda c: -c.score)
        # The top doc chunk always makes the list, so a draft can cite policy as well as the library.
        out = merged[:k]
        if chunks and chunks[0] not in out:
            out = out[: k - 1] + [chunks[0]]
        cov_q = f"{context} {query}" if context else query
        cov = self.coverage(cov_q, " ".join(f"{c.question} {c.text}" for c in out[:3]))
        if self.unknown_terms(query):
            cov = 0.0
        return Retrieval(out, superseded, conflicts, cov)

    def _apply_recency(self, answers: list[Candidate], chunks: list[Candidate]):
        superseded: list[dict] = []
        conflicts: list[dict] = []
        if not answers:
            return superseded, conflicts
        group = answers[:12]
        facts = {c.id: extract_facts(c.text) for c in group}
        dropped: set[str] = set()
        # 1. A newer policy doc that disagrees with an answer supersedes it.
        doc = chunks[0] if chunks and chunks[0].score >= 0.6 else None
        for c in group:
            if doc is None:
                break
            diff = facts_conflict(facts[c.id], best_sentence_facts(c.text, doc.text))
            if not diff:
                continue
            if doc.date > c.date:
                superseded.append({"id": c.id, "by": doc.id, "reason": f"older than policy {doc.id}: {diff[0]}"})
                dropped.add(c.id)
            else:
                conflicts.append({"ids": [c.id, doc.id], "detail": diff[0]})
        # 2. Between answers: the newer one wins when they are far apart in time; otherwise it is a conflict.
        live = [c for c in group if c.id not in dropped]
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                if a.id in dropped or b.id in dropped or not same_subject(a, b):
                    continue
                diff = facts_conflict(facts[a.id], facts[b.id])
                if not diff:
                    continue
                older, newer = (a, b) if a.date < b.date else (b, a)
                if newer.status != "approved" and older.status == "approved":
                    conflicts.append({"ids": [older.id, newer.id], "detail": diff[0] + " (newer one is a draft)"})
                elif _days(newer.date, older.date) > SUPERSEDE_GAP_DAYS:
                    superseded.append({"id": older.id, "by": newer.id,
                                       "reason": f"superseded by newer answer {newer.id}: {diff[0]}"})
                    dropped.add(older.id)
                else:
                    conflicts.append({"ids": [older.id, newer.id], "detail": diff[0]})
        return superseded, conflicts
