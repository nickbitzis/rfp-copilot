"""The answering pipeline: retrieve, abstain or draft, validate, and set a review status.

Status rules:
- sme: source coverage is too low, so the question goes to the subject matter expert queue unanswered.
- auto_approved: the draft reuses an approved library answer verbatim, the question matches the library
  question closely, confidence is at least 0.85, and no source conflict was found.
- needs_review: everything else, with the reason attached.
"""

from __future__ import annotations

import time

from .drafting import Draft, Drafter, ExtractiveDrafter, validate
from .kb import KnowledgeBase
from .parser import ParsedQuestionnaire, QuestionItem
from .retrieval import Retriever

SME_TEAMS = {
    "Compliance": "grc", "Access Control": "security", "Encryption": "security", "Data Protection": "privacy",
    "Infrastructure": "platform", "Business Continuity": "platform", "Incident Response": "security",
    "Vulnerability Management": "security", "Logging": "security", "Vendor Management": "grc",
    "SLA & Support": "support", "Product": "product", "Commercial": "legal", "HR Security": "people",
    "Secure Development": "engineering",
}
SME_KEYWORDS = {
    "insurance": "legal", "revenue": "finance", "financial": "finance", "price": "legal", "contract": "legal",
    "privacy": "privacy", "personal": "privacy", "fedramp": "grc", "certif": "grc", "audit": "grc",
    "encrypt": "security", "crypt": "security", "breach": "security", "employee": "people", "staff": "people",
    "customer": "sales", "carbon": "facilities", "data center": "platform", "deploy": "platform",
}


def sme_team(section: str, question: str) -> str:
    low = question.lower()
    for kw, team in SME_KEYWORDS.items():
        if kw in low:
            return team
    for name, team in SME_TEAMS.items():
        if name.lower() in section.lower() or section.lower() in name.lower():
            return team
    return "solutions"


class Pipeline:
    def __init__(self, kb: KnowledgeBase, drafter: Drafter | None = None, mode: str = "hybrid",
                 abstain_below: float = 0.35, auto_confidence: float = 0.85, k: int = 5):
        self.kb, self.mode = kb, mode
        self.retriever = Retriever(kb, mode)
        self.drafter = drafter or ExtractiveDrafter()
        self.abstain_below, self.auto_confidence, self.k = abstain_below, auto_confidence, k

    def refresh(self) -> None:
        """Rebuild indexes after the library changes (write-back)."""
        self.retriever.rebuild()

    def answer(self, question: str, context: str = "", section: str = "") -> dict:
        t0 = time.perf_counter()
        ret = self.retriever.retrieve(question, self.k, context)
        abstain = not ret.candidates or ret.coverage < self.abstain_below
        if abstain:
            team = sme_team(section, question)
            draft = Draft("", "unanswered", [], 0.0,
                          f"routed to the {team} SME queue: sources cover {ret.coverage:.0%} of the question")
            status, errors = "sme", []
        else:
            draft = self.drafter.draft(question, ret)
            sources = {c.id: f"{c.question} {c.text}" for c in ret.candidates}
            v = validate(draft, sources)
            errors = v.errors
            team = ""
            if not v.ok:
                draft.needs_review = "validator rejected the draft: " + "; ".join(v.errors)
                draft.confidence = min(draft.confidence, 0.3)
                draft.exact_match = None
            if draft.compliance == "unanswered":
                status, team = "sme", sme_team(section, question)
            elif (v.ok and draft.exact_match and draft.confidence >= self.auto_confidence
                  and not ret.conflicts):
                status = "auto_approved"
                draft.needs_review = None
            else:
                status = "needs_review"
        return {
            "question_text": question,
            "draft": draft.to_dict(),
            "status": status,
            "sme_team": team,
            "coverage": round(ret.coverage, 3),
            "sources": [c.public() for c in ret.candidates],
            "superseded": ret.superseded,
            "conflicts": ret.conflicts,
            "validation_errors": errors,
            "final_answer": draft.answer if status == "auto_approved" else "",
            "final_compliance": draft.compliance if status == "auto_approved" else "",
            "approved_by": "auto" if status == "auto_approved" else "",
            "edits": [],
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        }

    def process_item(self, item: QuestionItem) -> dict:
        out = self.answer(item.text, item.context, item.section)
        out.update(item.to_dict())
        return out

    def process(self, parsed: ParsedQuestionnaire) -> list[dict]:
        return [self.process_item(it) for it in parsed.items]
