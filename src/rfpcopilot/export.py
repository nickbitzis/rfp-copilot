"""Fill answers back into the customer's original file, and build the compliance matrix.

The export opens the original workbook (or CSV) and writes only the answer and yes/no cells of question rows.
Titles, merged cells, column widths, styles, other sheets, and every other cell stay as they were.
Answers go out without citation markers. Questions still waiting for review are left blank by default.
"""

from __future__ import annotations

import csv
import io
from collections import OrderedDict

from .text import strip_citations

LABEL = {"yes": "Yes", "no": "No", "partial": "Partial", "unanswered": ""}
DONE = ("approved", "auto_approved")


def _answer_of(it: dict, include_drafts: bool) -> tuple[str, str]:
    if it["status"] in DONE:
        return strip_citations(it["final_answer"] or it["draft"]["answer"]), (
            it["final_compliance"] or it["draft"]["compliance"])
    if include_drafts and it["status"] == "needs_review":
        return strip_citations(it["final_answer"] or it["draft"]["answer"]), it["draft"]["compliance"]
    return "", "unanswered"


def combine_compliance(values: list[str]) -> str:
    if not values or any(v == "unanswered" for v in values):
        return "unanswered"
    if all(v == values[0] for v in values):
        return values[0]
    return "partial"


def row_answers(items: list[dict], include_drafts: bool = False) -> OrderedDict[int, dict]:
    """Group question parts back into their row: 'a) ... b) ...' text and one combined compliance value."""
    rows: OrderedDict[int, dict] = OrderedDict()
    for it in items:
        text, comp = _answer_of(it, include_drafts)
        r = rows.setdefault(it["row"], {"section": it["section"], "question": it["question"], "parts": []})
        r["parts"].append((it["part"], text, comp))
    for r in rows.values():
        parts = r["parts"]
        if len(parts) == 1:
            r["text"] = parts[0][1]
        else:
            r["text"] = "\n".join(f"{p}) {t}" for p, t, _ in parts if t) if any(t for _, t, _ in parts) else ""
        r["compliance"] = combine_compliance([c for _, _, c in parts])
    return rows


def export_file(content: bytes, fmt: str, layout: dict, items: list[dict], include_drafts: bool = False) -> bytes:
    rows = row_answers(items, include_drafts)
    qa, yn = layout["answer_col"], layout["yesno_col"]
    if fmt == "csv":
        grid = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
        width = max(len(r) for r in grid)
        for r, ans in rows.items():
            grid[r] += [""] * (width - len(grid[r]))
            if yn is not None:
                grid[r][yn] = LABEL[ans["compliance"]]
                grid[r][qa] = ans["text"]
            else:
                lead = LABEL[ans["compliance"]]
                grid[r][qa] = f"{lead}. {_drop_lead(ans['text'])}" if lead and ans["text"] else ans["text"]
        buf = io.StringIO()
        csv.writer(buf, lineterminator="\n").writerows(grid)
        return buf.getvalue().encode()
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment

    wb = load_workbook(io.BytesIO(content))
    ws = wb[layout["sheet"]] if layout.get("sheet") else wb.active
    for r, ans in rows.items():
        cell = ws.cell(r + 1, qa + 1)
        cell.value = (_drop_lead(ans["text"]) if yn is not None else ans["text"]) or None
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if yn is not None:
            ws.cell(r + 1, yn + 1).value = LABEL[ans["compliance"]] or None
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _drop_lead(text: str) -> str:
    """With a separate Yes/No column the explanation does not need to repeat 'Yes.'."""
    for lead in ("Yes. ", "No. ", "Partial. "):
        if text.startswith(lead):
            return text[len(lead):]
    return text


def compliance_matrix(items: list[dict], include_drafts: bool = False) -> dict:
    rows = row_answers(items, include_drafts)
    keys = ("yes", "no", "partial", "unanswered")
    total = dict.fromkeys(keys, 0)
    by_section: OrderedDict[str, dict] = OrderedDict()
    for r in rows.values():
        sec = by_section.setdefault(r["section"], dict.fromkeys(keys, 0))
        sec[r["compliance"]] += 1
        total[r["compliance"]] += 1
    status = {}
    for it in items:
        status[it["status"]] = status.get(it["status"], 0) + 1
    return {"questions": len(rows), "parts": len(items), "total": total, "by_section": by_section,
            "status": status}


def matrix_csv(matrix: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["Section", "Yes", "No", "Partial", "Unanswered", "Total"])
    for sec, c in matrix["by_section"].items():
        w.writerow([sec, c["yes"], c["no"], c["partial"], c["unanswered"], sum(c.values())])
    t = matrix["total"]
    w.writerow(["All", t["yes"], t["no"], t["partial"], t["unanswered"], sum(t.values())])
    return buf.getvalue()
