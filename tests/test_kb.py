from rfpcopilot.kb import build_kb, load_kb, save_kb


def test_corpus_size(kb, truth):
    assert len(kb.docs) == 60
    assert 290 <= len(kb.library) <= 320
    assert len(truth["outdated"]) >= 20
    assert truth["contradictory"]


def test_library_entries_have_metadata(kb):
    for a in kb.library:
        assert a.id.startswith("A-") and a.approver and a.date and a.product_version and a.tags
        assert a.compliance in ("yes", "no", "partial")


def test_outdated_answers_are_older_than_current(kb, truth):
    by_id = {a.id: a for a in kb.library}
    for key, ids in truth["current"].items():
        newest_old = [by_id[i].date for i in truth["outdated"] if truth["topic_of"][i] == key]
        if newest_old:
            assert max(newest_old) < min(by_id[i].date for i in ids)


def test_chunks_have_stable_ids(kb):
    ids = [c.id for c in kb.chunks]
    assert len(ids) == len(set(ids))
    assert kb.chunk("pol-encryption#1").doc_id == "pol-encryption"


def test_generation_is_deterministic():
    a, _ = build_kb()
    b, _ = build_kb()
    assert [x.answer for x in a.library] == [x.answer for x in b.library]


def test_save_and_load_round_trip(kb, tmp_path):
    save_kb(kb, tmp_path)
    loaded = load_kb(tmp_path)
    assert len(loaded.docs) == len(kb.docs)
    assert sorted(c.id for c in loaded.chunks) == sorted(c.id for c in kb.chunks)
    assert loaded.library[5] == kb.library[5]
