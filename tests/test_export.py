import csv
import io

import pytest
from openpyxl import load_workbook

from rfpcopilot.export import combine_compliance, compliance_matrix, export_file, matrix_csv
from rfpcopilot.parser import parse_file
from rfpcopilot.samples import sample_bytes


def run(pipeline, name):
    content = sample_bytes(name)
    parsed = parse_file(content, name)
    return content, parsed, pipeline.process(parsed)


def cells(wb):
    return {ws.title: [[c.value for c in row] for row in ws.iter_rows()] for ws in wb.worksheets}


@pytest.mark.parametrize("name", ["tallis-freight-security.xlsx", "okafor-retail-due-diligence.xlsx"])
def test_xlsx_round_trip_preserves_layout(pipeline, name):
    content, parsed, items = run(pipeline, name)
    out = export_file(content, "xlsx", parsed.layout.to_dict(), items, include_drafts=True)
    before, after = load_workbook(io.BytesIO(content)), load_workbook(io.BytesIO(out))
    assert before.sheetnames == after.sheetnames
    for ws_b, ws_a in zip(before.worksheets, after.worksheets, strict=True):
        assert sorted(map(str, ws_b.merged_cells.ranges)) == sorted(map(str, ws_a.merged_cells.ranges))
        assert {k: v.width for k, v in ws_b.column_dimensions.items()} == {
            k: v.width for k, v in ws_a.column_dimensions.items()}
    lay = parsed.layout
    b, a = cells(before), cells(after)
    for sheet in b:
        for r, (rb, ra) in enumerate(zip(b[sheet], a[sheet], strict=True)):
            for c, (vb, va) in enumerate(zip(rb, ra, strict=True)):
                if sheet == lay.sheet and c in (lay.answer_col, lay.yesno_col) and r in {i["row"] for i in items}:
                    continue
                assert vb == va, (sheet, r, c)
    reparsed = parse_file(out, name)
    assert [i.text for i in reparsed.items] == [i.text for i in parsed.items]


def test_xlsx_answers_land_in_answer_and_yes_no_columns(pipeline):
    content, parsed, items = run(pipeline, "tallis-freight-security.xlsx")
    out = export_file(content, "xlsx", parsed.layout.to_dict(), items)
    ws = load_workbook(io.BytesIO(out))["Security Questionnaire"]
    auto = next(i for i in items if i["status"] == "auto_approved" and not i["part"])
    r = auto["row"] + 1
    assert ws.cell(r, 3).value in ("Yes", "No", "Partial")
    assert ws.cell(r, 4).value and "[" not in ws.cell(r, 4).value  # no citation markers for the customer
    pending = next(i for i in items if i["status"] == "needs_review")
    assert ws.cell(pending["row"] + 1, 4).value is None  # drafts are not exported unless asked


def test_multi_part_answers_are_combined_in_one_cell(pipeline):
    content, parsed, items = run(pipeline, "tallis-freight-security.xlsx")
    out = export_file(content, "xlsx", parsed.layout.to_dict(), items, include_drafts=True)
    ws = load_workbook(io.BytesIO(out))["Security Questionnaire"]
    row = next(i["row"] for i in items if i["part"] == "a")
    text = ws.cell(row + 1, 4).value
    assert text.startswith("a) ") and "\nb) " in text


def test_csv_round_trip(pipeline):
    content, parsed, items = run(pipeline, "merrow-health-rfp.csv")
    out = export_file(content, "csv", parsed.layout.to_dict(), items, include_drafts=True)
    before = list(csv.reader(io.StringIO(content.decode())))
    after = list(csv.reader(io.StringIO(out.decode())))
    assert len(before) == len(after)
    for rb, ra in zip(before, after, strict=True):
        assert rb[:3] == ra[:3]
    answered = [r for r in after[3:] if r[3]]
    assert len(answered) >= len(after[3:]) - 3
    assert answered[0][3].split(".")[0] in ("Yes", "No", "Partial")


def test_compliance_matrix_counts(pipeline):
    _, parsed, items = run(pipeline, "okafor-retail-due-diligence.xlsx")
    m = compliance_matrix(items, include_drafts=True)
    assert m["questions"] == len({i["row"] for i in items})
    assert sum(m["total"].values()) == m["questions"]
    assert m["total"]["unanswered"] >= 2
    assert sum(sum(v.values()) for v in m["by_section"].values()) == m["questions"]
    text = matrix_csv(m)
    assert text.splitlines()[0].startswith("Section,Yes,No") and text.splitlines()[-1].startswith("All,")


def test_combine_compliance():
    assert combine_compliance(["yes", "yes"]) == "yes"
    assert combine_compliance(["yes", "no"]) == "partial"
    assert combine_compliance(["yes", "unanswered"]) == "unanswered"
