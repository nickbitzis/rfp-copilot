"""Offline evaluation on the labeled question set, comparing retrieval configurations.

Metrics:
- recall@5: share of answerable questions with at least one gold source in the top 5 retrieved.
- citation precision: share of cited sources that are gold sources for the question.
- answer accuracy: share of answered questions the judge marks correct (gold facts present, no stale value).
- correct abstention: share of unanswerable questions routed to the SME queue instead of answered.
- false abstention: share of answerable questions routed to the SME queue.
- outdated-source usage: share of answered questions that cite a superseded library answer. Must be near 0.
- auto-approved share and its precision, and the time saved estimate.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from .drafting import Drafter
from .kb import build_kb
from .pipeline import Pipeline
from .samples import build_eval_set
from .text import strip_citations

MINUTES_PER_QUESTION = 12  # typical time for a solutions engineer to find, adapt, and get sign-off on one answer


class Judge(Protocol):
    name: str

    def grade(self, question: str, answer: str, gold_facts: list[str], gold_answer: str) -> bool: ...


class FactJudge:
    """Offline judge: correct when every gold fact appears in the answer."""

    name = "facts"

    def grade(self, question, answer, gold_facts, gold_answer) -> bool:
        low = answer.lower()
        return bool(gold_facts) and all(re.search(rf"(?<![\w.]){re.escape(f.lower())}(?![\w])", low)
                                        for f in gold_facts)


class ClaudeJudge:
    """LLM-as-judge behind the same interface. Not used in CI."""

    name = "claude"
    SCHEMA = {"type": "object", "properties": {"correct": {"type": "boolean"}, "reason": {"type": "string"}},
              "required": ["correct", "reason"], "additionalProperties": False}

    def __init__(self, client=None, model: str = "claude-opus-5-5"):
        if client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("Install the Claude extra first: uv sync --extra claude") from exc
            client = anthropic.Anthropic()
        self.client, self.model = client, model

    def grade(self, question, answer, gold_facts, gold_answer) -> bool:
        prompt = (f"<question>{question}</question>\n<reference>{gold_answer}</reference>\n"
                  f"<candidate>{answer}</candidate>\nIs the candidate factually consistent with the reference and "
                  "does it answer the question? Return JSON.")
        r = self.client.messages.create(model=self.model, max_tokens=512,
                                        output_config={"format": {"type": "json_schema", "schema": self.SCHEMA}},
                                        messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        try:
            return bool(json.loads(text)["correct"])
        except (ValueError, KeyError):
            return False


@dataclass
class Report:
    mode: str
    n: int
    recall_at_5: float
    citation_precision: float
    answer_accuracy: float
    correct_abstention: float
    false_abstention: float
    outdated_usage: float
    conflict_flags: int
    auto_approved_share: float
    auto_approved_precision: float
    minutes_saved_per_100: float
    failures: list[dict]

    def row(self) -> dict:
        d = dict(self.__dict__)
        d.pop("failures")
        return d


def _ratio(a: float, b: float) -> float:
    return round(a / b, 4) if b else 0.0


def run_eval(mode: str = "hybrid", drafter: Drafter | None = None, judge: Judge | None = None,
             eval_set: dict | None = None) -> Report:
    kb, _ = build_kb()
    es = eval_set or build_eval_set()
    outdated = set(es["outdated_ids"])
    pipe = Pipeline(kb, drafter, mode=mode)
    judge = judge or FactJudge()
    hits = cited = cited_good = answered = correct = 0
    abst_ok = abst_bad = used_outdated = conflicts = auto = auto_ok = 0
    n_ans = sum(1 for i in es["items"] if i["answerable"])
    n_unans = len(es["items"]) - n_ans
    failures = []
    for item in es["items"]:
        res = pipe.answer(item["question"], section=item["section"])
        top5 = [s["id"] for s in res["sources"][:5]]
        d = res["draft"]
        abstained = res["status"] == "sme"
        conflicts += bool(res["conflicts"])
        if not item["answerable"]:
            abst_ok += abstained
            if not abstained:
                failures.append({"id": item["id"], "why": "answered an unanswerable question", "cited": d["citations"]})
            continue
        gold = set(item["gold_sources"])
        hits += bool(gold & set(top5))
        if abstained:
            abst_bad += 1
            failures.append({"id": item["id"], "why": f"abstained (coverage {res['coverage']})"})
            continue
        answered += 1
        cited += len(d["citations"])
        cited_good += len(gold & set(d["citations"]))
        stale = outdated & set(d["citations"])
        used_outdated += bool(stale)
        ok = judge.grade(item["question"], strip_citations(d["answer"]), item["gold_facts"], item["gold_answer"])
        ok = ok and not stale
        correct += ok
        if res["status"] == "auto_approved":
            auto += 1
            auto_ok += ok
        if not ok:
            failures.append({"id": item["id"], "why": "stale source" if stale else "wrong or incomplete answer",
                             "cited": d["citations"]})
    n = len(es["items"])
    return Report(
        mode=mode, n=n,
        recall_at_5=_ratio(hits, n_ans),
        citation_precision=_ratio(cited_good, cited),
        answer_accuracy=_ratio(correct, answered),
        correct_abstention=_ratio(abst_ok, n_unans),
        false_abstention=_ratio(abst_bad, n_ans),
        outdated_usage=_ratio(used_outdated, answered),
        conflict_flags=conflicts,
        auto_approved_share=_ratio(auto, n),
        auto_approved_precision=_ratio(auto_ok, auto),
        minutes_saved_per_100=round(100 * _ratio(auto, n) * MINUTES_PER_QUESTION, 1),
        failures=failures,
    )


ROWS = [
    ("recall_at_5", "Retrieval recall@5", "pct"), ("citation_precision", "Citation precision", "pct"),
    ("answer_accuracy", "Answer accuracy (judge)", "pct"), ("correct_abstention", "Correct abstention", "pct"),
    ("false_abstention", "False abstention", "pct"), ("outdated_usage", "Outdated-source usage", "pct"),
    ("conflict_flags", "Questions with a conflict flag", "int"),
    ("auto_approved_share", "Auto-approved share", "pct"),
    ("auto_approved_precision", "Auto-approved precision", "pct"),
    ("minutes_saved_per_100", "Minutes saved per 100 questions", "num"),
]


def markdown_table(reports: list[Report]) -> str:
    head = "| Metric | " + " | ".join(r.mode for r in reports) + " |\n|---|" + "---:|" * len(reports) + "\n"
    lines = []
    for key, label, kind in ROWS:
        vals = []
        for r in reports:
            v = getattr(r, key)
            vals.append(f"{v * 100:.1f}%" if kind == "pct" else (str(v) if kind == "int" else f"{v:.0f}"))
        lines.append(f"| {label} | " + " | ".join(vals) + " |")
    return head + "\n".join(lines) + "\n"


def gate(report: Report, max_outdated: float, min_abstention: float, min_recall: float = 0.0) -> list[str]:
    problems = []
    if report.outdated_usage > max_outdated:
        problems.append(f"outdated-source usage {report.outdated_usage:.1%} is above {max_outdated:.0%}")
    if report.correct_abstention < min_abstention:
        problems.append(f"correct abstention {report.correct_abstention:.1%} is below {min_abstention:.0%}")
    if report.recall_at_5 < min_recall:
        problems.append(f"recall@5 {report.recall_at_5:.1%} is below {min_recall:.0%}")
    return problems


def questionnaire_savings(minutes: int = MINUTES_PER_QUESTION) -> list[dict]:
    """Auto-approval share on the three sample questionnaires, which mix library wording with new wording."""
    from .parser import parse_file
    from .samples import SAMPLES, sample_bytes

    pipe = Pipeline(build_kb()[0])
    out = []
    for name in SAMPLES:
        items = pipe.process(parse_file(sample_bytes(name), name))
        auto = sum(i["status"] == "auto_approved" for i in items)
        sme = sum(i["status"] == "sme" for i in items)
        out.append({"file": name, "parts": len(items), "auto_approved": auto, "needs_review": len(items) - auto - sme,
                    "sme": sme, "minutes_saved": auto * minutes})
    return out
