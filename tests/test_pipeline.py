from rfpcopilot.drafting import ClaudeDrafter
from rfpcopilot.pipeline import Pipeline, sme_team


def test_unanswerable_goes_to_sme_queue(pipeline):
    r = pipeline.answer("What is the coverage limit of your cyber liability insurance policy?")
    assert r["status"] == "sme" and r["draft"]["compliance"] == "unanswered"
    assert r["sme_team"] == "legal" and r["draft"]["answer"] == ""


def test_library_question_is_auto_approved(pipeline):
    r = pipeline.answer("Do you support SCIM?")
    assert r["status"] == "auto_approved" and r["final_answer"] and r["approved_by"] == "auto"
    assert r["draft"]["confidence"] >= 0.85


def test_paraphrase_needs_review(pipeline):
    r = pipeline.answer("How frequently does an outside firm run a penetration test against the application?")
    assert r["status"] == "needs_review"
    assert "6 months" in r["draft"]["answer"]


def test_conflict_blocks_auto_approval(pipeline):
    r = pipeline.answer("What are your RPO and RTO?")
    assert r["conflicts"] and r["status"] == "needs_review"
    assert "sources disagree" in r["draft"]["needs_review"]
    assert "8 hours" in r["draft"]["answer"]  # the answer the policy doc backs


def test_follow_up_uses_context(pipeline):
    r = pipeline.answer("If so, how often?", context="Do you conduct penetration testing?")
    assert "6 months" in r["draft"]["answer"]


def test_claude_drafts_never_auto_approve(kb, fake_claude):
    def reply(kwargs):
        content = kwargs["messages"][0]["content"]
        aid = content.split('source id="')[1].split('"')[0]
        return {"answer": f"Yes. [{aid}]", "compliance": "yes", "citations": [aid], "confidence": 0.99,
                "needs_review": None}
    p = Pipeline(kb, ClaudeDrafter(fake_claude(reply)))
    r = p.answer("Do you support SCIM?")
    assert r["status"] == "needs_review"


def test_sme_team_routing():
    assert sme_team("Commercial", "What is our discount?") == "legal"
    assert sme_team("", "What percentage of revenue is spent on security?") == "finance"
    assert sme_team("Unknown", "Something else entirely") == "solutions"
