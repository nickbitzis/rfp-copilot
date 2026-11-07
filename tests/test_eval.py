import pytest

from rfpcopilot.evaluate import FactJudge, gate, markdown_table, run_eval
from rfpcopilot.samples import build_eval_set


@pytest.fixture(scope="module")
def reports():
    return run_eval("bm25"), run_eval("hybrid")


def test_eval_set_shape():
    es = build_eval_set()
    assert len(es["items"]) == 80
    assert sum(not i["answerable"] for i in es["items"]) == 10
    assert all(i["gold_sources"] for i in es["items"] if i["answerable"])


def test_hybrid_passes_the_gate(reports):
    hybrid = reports[1]
    assert gate(hybrid, max_outdated=0.02, min_abstention=0.8, min_recall=0.9) == []
    assert hybrid.outdated_usage == 0.0
    assert hybrid.citation_precision >= 0.9 and hybrid.answer_accuracy >= 0.85


def test_bm25_only_uses_outdated_sources(reports):
    bm25, hybrid = reports
    assert bm25.outdated_usage > 0.05 > hybrid.outdated_usage
    assert gate(bm25, 0.02, 0.8)


def test_auto_approved_answers_are_correct(reports):
    assert reports[1].auto_approved_precision == 1.0


def test_gate_reports_each_problem(reports):
    bad = reports[1]
    problems = gate(bad, max_outdated=-1, min_abstention=1.1, min_recall=1.1)
    assert len(problems) == 3


def test_fact_judge():
    j = FactJudge()
    assert j.grade("q", "Backups run every 4 hours and are kept 35 days.", ["4 hours", "35 days"], "")
    assert not j.grade("q", "Backups run every 24 hours.", ["4 hours"], "")


def test_markdown_table(reports):
    t = markdown_table(list(reports))
    assert t.startswith("| Metric | bm25 | hybrid |") and "Outdated-source usage" in t
