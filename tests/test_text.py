from rfpcopilot.text import (
    BM25,
    extract_facts,
    facts_conflict,
    find_citations,
    question_similarity,
    stem,
    strip_citations,
    tokenize,
)


def test_tokenize_drops_stopwords_and_expands_acronyms():
    toks = tokenize("Do you support SSO?")
    assert "single" in toks and "sign" in toks
    assert "you" not in toks and "support" not in toks


def test_stem_handles_doubled_consonants():
    assert stem("scanned") == stem("scan") == "scan"
    assert stem("policies") == "policy"


def test_bm25_ranks_matching_doc_first():
    idx = BM25([tokenize("backups are encrypted"), tokenize("password length rules"), tokenize("pricing plans")])
    scores = idx.scores(tokenize("password policy"))
    assert scores.index(max(scores)) == 1


def test_question_similarity_orders_paraphrases():
    a = question_similarity("Do you support SSO?", "Do you support single sign-on?")
    b = question_similarity("Do you support SSO?", "What are your payment terms?")
    assert a > 0.8 > b


def test_extract_facts_units_versions_and_polarity():
    f = extract_facts("Yes. All connections use TLS 1.2 or higher. Logs are kept for 13 months and 90 days online.")
    assert f["tls"] == {"1.2"}
    assert f["month"] == {"13"}
    assert f["day"] == {"90"}
    assert f["polarity"] == {"yes"}


def test_extract_facts_ignores_dates():
    assert "polarity" not in extract_facts("The last test was completed on 2026-04-14.")
    assert extract_facts("The last test was completed on 2026-04-14.") == {}


def test_facts_conflict_detects_disagreement_but_allows_subsets():
    old = extract_facts("Critical vulnerabilities are remediated within 30 days and high within 60 days.")
    new = extract_facts("Critical within 7 days, high within 30 days, and medium within 90 days.")
    assert facts_conflict(old, new)
    short = extract_facts("Critical vulnerabilities are fixed within 7 days.")
    assert not facts_conflict(short, new)


def test_citation_helpers():
    text = "Yes. Data is encrypted with AES-256. [A-0012][pol-encryption#1]"
    assert find_citations(text) == ["A-0012", "pol-encryption#1"]
    assert strip_citations(text) == "Yes. Data is encrypted with AES-256."
