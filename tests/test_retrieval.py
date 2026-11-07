from rfpcopilot.retrieval import Retriever


def test_exact_library_question_ranks_first(kb, truth):
    r = Retriever(kb).retrieve("What is your password policy?")
    top = [c for c in r.candidates if c.kind == "answer"][0]
    assert truth["topic_of"][top.id] == "password"
    assert top.qsim >= 0.95


def test_policy_chunk_is_always_included(kb, truth):
    r = Retriever(kb).retrieve("Is data encrypted at rest?")
    assert truth["doc_chunk"]["enc-rest"] in [c.id for c in r.candidates]


def test_recency_rule_drops_outdated_answers(kb, truth):
    r = Retriever(kb).retrieve("How often are third-party penetration tests performed?", k=5)
    ids = {c.id for c in r.candidates}
    old = {i for i in truth["outdated"] if truth["topic_of"][i] == "pentest"}
    assert not ids & old
    assert {s["id"] for s in r.superseded} & old


def test_bm25_only_keeps_outdated_answers(kb, truth):
    old = set(truth["outdated"])
    hits = 0
    for q in ["How long are logs retained?", "What is your uptime SLA?", "What are your payment terms?",
              "Which TLS versions do you support?", "How often are user access rights reviewed?"]:
        hits += bool({c.id for c in Retriever(kb, "bm25").retrieve(q).candidates} & old)
    assert hits >= 3


def test_conflict_between_current_answers_is_flagged(kb, truth):
    r = Retriever(kb).retrieve("What are your RPO and RTO?")
    assert r.conflicts
    flagged = {i for c in r.conflicts for i in c["ids"]}
    assert set(truth["contradictory"]) & flagged


def test_answers_to_different_questions_do_not_supersede_each_other(kb, truth):
    r = Retriever(kb).retrieve("Under what conditions can your support staff access our workspace?")
    for s in r.superseded:
        assert truth["topic_of"].get(s["id"]) == truth["topic_of"].get(s["by"], truth["topic_of"].get(s["id"]))


def test_drafts_rank_below_approved(kb):
    a = next(x for x in kb.library if x.status == "approved" and x.date >= "2026")
    twin = type(a)(**{**a.__dict__, "id": "A-9999", "status": "draft", "date": "2026-10-30"})
    kb.library.append(twin)
    r = Retriever(kb).retrieve(a.question)
    order = [c.id for c in r.candidates]
    assert "A-9999" not in order[:1]


def test_unknown_named_standard_drops_coverage(kb):
    r = Retriever(kb).retrieve("Do you hold a CMMC Level 2 certification?")
    assert r.coverage == 0.0
    r2 = Retriever(kb).retrieve("Are you ISO 27001 certified?")
    assert r2.coverage > 0.5
