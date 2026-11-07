import io

import pytest
from openpyxl import Workbook

from rfpcopilot.parser import ParseError, parse_file, parse_rows, split_parts
from rfpcopilot.samples import sample_bytes


def xlsx(build) -> bytes:
    wb = Workbook()
    build(wb.active)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_tallis_sample_layout_and_sections():
    p = parse_file(sample_bytes("tallis-freight-security.xlsx"), "tallis-freight-security.xlsx")
    lay = p.layout
    assert lay.header_row == 4  # title and instruction rows above the header
    assert (lay.id_col, lay.question_col, lay.yesno_col, lay.answer_col) == (0, 1, 2, 3)
    sections = {it.section for it in p.items}
    assert "Governance and Compliance" in sections and "Resilience" in sections
    assert all(not it.text.startswith(("1.", "2.")) for it in p.items)


def test_merged_section_rows_are_not_questions():
    p = parse_file(sample_bytes("tallis-freight-security.xlsx"), "x.xlsx")
    assert not any(it.text.startswith("2. Identity") for it in p.items)
    assert p.items[0].section == "Governance and Compliance"


def test_csv_with_preamble_and_category_column():
    p = parse_file(sample_bytes("merrow-health-rfp.csv"), "merrow-health-rfp.csv")
    assert p.layout.header_row == 2
    assert p.layout.section_col == 1 and p.layout.id_col == 0 and p.layout.yesno_col is None
    assert p.items[0].ref == "MHP-001" and p.items[0].section == "Security"


def test_okafor_yes_no_partial_column_detected():
    p = parse_file(sample_bytes("okafor-retail-due-diligence.xlsx"), "o.xlsx")
    assert p.layout.yesno_col == 3 and p.layout.answer_col == 4 and p.layout.question_col == 2


def test_split_lettered_parts_keeps_stem_as_context():
    parts = split_parts("Regarding the architecture: a) What are the main components? b) Do you use a WAF? "
                        "c) Are servers hardened?")
    assert [p[0] for p in parts] == ["a", "b", "c"]
    assert parts[1][1] == "Do you use a WAF?"
    assert parts[0][2] == "Regarding the architecture"


def test_split_roman_numerals():
    parts = split_parts("(i) Which browsers are supported? (ii) Do you provide a sandbox environment?")
    assert [p[0] for p in parts] == ["i", "ii"]


def test_split_follow_up_question_gets_context():
    parts = split_parts("Do you have an incident response plan? If so, how quickly will you notify us of a breach?")
    assert len(parts) == 2
    assert parts[1][2] == "Do you have an incident response plan?"


def test_single_question_is_not_split():
    assert split_parts("Describe your network security controls.") == [
        ("", "Describe your network security controls.", "")]
    assert len(split_parts("Is data encrypted? Yes")) == 1


def test_multi_part_items_share_the_row():
    p = parse_file(sample_bytes("okafor-retail-due-diligence.xlsx"), "o.xlsx")
    parts = [it for it in p.items if it.part]
    assert len({it.row for it in parts}) == 1 and len(parts) == 3
    assert parts[0].item_id.endswith(".a")


def test_header_detection_with_unusual_names():
    rows = [["Security review"], [], ["No.", "Control description", "Vendor comments"],
            ["1", "Is data encrypted at rest?", ""], ["2", "Do you support SSO?", ""]]
    p = parse_rows(rows, "csv")
    assert p.layout.question_col == 1 and p.layout.answer_col == 2 and len(p.items) == 2


def test_fallback_without_header_uses_longest_column():
    rows = [["1", "Is customer data encrypted at rest with strong ciphers?"],
            ["2", "Do you perform penetration tests every year?"]]
    p = parse_rows(rows, "csv")
    assert p.layout.question_col == 1 and p.layout.answer_col == 2 and len(p.items) == 2


def test_section_row_in_plain_xlsx():
    def build(ws):
        ws.append(["Question", "Answer"])
        ws.append(["Encryption"])
        ws.append(["Is data encrypted at rest?", None])
    p = parse_file(xlsx(build), "s.xlsx")
    assert p.items[0].section == "Encryption" and len(p.items) == 1


def test_errors_on_empty_and_unsupported():
    with pytest.raises(ParseError):
        parse_rows([["Question", "Answer"]], "csv")
    with pytest.raises(ParseError):
        parse_file(b"x", "notes.pdf")
