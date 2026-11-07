"""Questionnaire parser for messy CSV and XLSX files.

What it handles:
- title and instruction rows above the header, and a header that is not on row 1,
- detecting the question, answer, yes/no, id, and section columns from header wording, with a fallback when
  there is no recognizable header,
- section rows (merged cells across the table, or a single filled cell) and section columns,
- multi-part questions: "a) ... b) ...", "(i) ... (ii) ...", and several questions in one cell, where a
  follow-up such as "If so, how often?" keeps the earlier part as retrieval context.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import asdict, dataclass, field

QUESTION_HDR = re.compile(r"question|requirement|control|query|item description|description", re.I)
YESNO_HDR = re.compile(r"yes\s*/\s*no|y\s*/\s*n|compliant|compliance|\(y", re.I)
ANSWER_HDR = re.compile(r"response|answer|comment|explanation|detail|remarks|vendor", re.I)
ID_HDR = re.compile(r"^\s*(#|id|ref|ref\.?|no\.?|number|req(uirement)? id|item)\s*$", re.I)
SECTION_HDR = re.compile(r"section|category|domain|area|topic", re.I)


@dataclass
class Layout:
    fmt: str  # csv | xlsx
    sheet: str | None
    header_row: int  # 0-based index into rows
    question_col: int
    answer_col: int
    yesno_col: int | None = None
    id_col: int | None = None
    section_col: int | None = None
    n_cols: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QuestionItem:
    item_id: str
    row: int  # 0-based index into rows (xlsx row number is row + 1)
    section: str
    ref: str
    question: str  # full cell text
    part: str  # "" for single questions, else "a", "b", "1", ...
    text: str  # the part's own text
    context: str = ""  # earlier text that a follow-up depends on

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParsedQuestionnaire:
    layout: Layout
    items: list[QuestionItem]
    rows: list[list[str]] = field(repr=False, default_factory=list)


class ParseError(ValueError):
    pass


def _cell(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def read_rows(data: bytes, fmt: str) -> tuple[str | None, list[list[str]]]:
    if fmt == "csv":
        text = data.decode("utf-8-sig")
        return None, [[c.strip() for c in r] for r in csv.reader(io.StringIO(text))]
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), data_only=True)
    best: tuple[int, str, list[list[str]]] | None = None
    for ws in wb.worksheets:
        rows = [[_cell(v) for v in r] for r in ws.iter_rows(values_only=True)]
        found = find_header(rows)
        score = found[1] if found else 0
        if best is None or score > best[0]:
            best = (score, ws.title, rows)
    assert best is not None
    return best[1], best[2]


def find_header(rows: list[list[str]]) -> tuple[int, int] | None:
    best = None
    for i, row in enumerate(rows[:20]):
        cells = [c for c in row if c]
        if len(cells) < 2:
            continue
        has_q = any(QUESTION_HDR.search(c) and len(c) < 40 for c in cells)
        has_a = any((ANSWER_HDR.search(c) or YESNO_HDR.search(c)) and len(c) < 40 for c in cells)
        score = 2 * has_q + 2 * has_a + (len(cells) >= 3)
        if has_q and has_a and (best is None or score > best[1]):
            best = (i, score)
    return best


def detect_layout(rows: list[list[str]], fmt: str, sheet: str | None) -> Layout:
    n_cols = max((len(r) for r in rows), default=0)
    found = find_header(rows)
    if found is None:
        return _fallback_layout(rows, fmt, sheet, n_cols)
    hi = found[0]
    header = rows[hi] + [""] * (n_cols - len(rows[hi]))
    roles: dict[str, int] = {}
    for j, h in enumerate(header):
        if not h:
            continue
        if "id" not in roles and ID_HDR.match(h):
            roles["id"] = j
        elif "yesno" not in roles and YESNO_HDR.search(h):
            roles["yesno"] = j
        elif "question" not in roles and QUESTION_HDR.search(h) and not ANSWER_HDR.search(h):
            roles["question"] = j
        elif "section" not in roles and SECTION_HDR.search(h):
            roles["section"] = j
        elif "answer" not in roles and ANSWER_HDR.search(h):
            roles["answer"] = j
    if "question" not in roles:
        raise ParseError("found a header row but no question column")
    if "answer" not in roles:
        if "yesno" in roles:
            roles["answer"] = roles.pop("yesno")
        else:
            raise ParseError("found a header row but no answer column")
    return Layout(fmt, sheet, hi, roles["question"], roles["answer"], roles.get("yesno"), roles.get("id"),
                  roles.get("section"), n_cols)


def _fallback_layout(rows, fmt, sheet, n_cols) -> Layout:
    """No header: the question column has the longest text; answers go in the first column to its right."""
    if not rows or n_cols == 0:
        raise ParseError("empty sheet")
    lengths = [0.0] * n_cols
    for r in rows:
        for j, c in enumerate(r):
            lengths[j] += len(c)
    q = max(range(n_cols), key=lambda j: lengths[j])
    a = q + 1
    return Layout(fmt, sheet, -1, q, a, None, None, None, max(n_cols, a + 1))


# ---- multi-part splitting ---------------------------------------------------------------------

_ENUM = re.compile(r"(?:^|\s|\n)\(?((?:[a-h])|(?:i{1,3}|iv|v|vi))\)\s+")
_FOLLOW_UP = re.compile(r"^(if (so|yes|not|applicable|no)|and if|please also|also,?)\b", re.I)


def split_parts(text: str) -> list[tuple[str, str, str]]:
    """Returns [(label, part text, context)]. A single question returns [("", text, "")]."""
    text = text.strip()
    marks = list(_ENUM.finditer(text))
    labels = [m.group(1) for m in marks]
    if len(marks) >= 2 and labels[0] in ("a", "i"):
        stem = text[: marks[0].start()].strip().rstrip(":").strip()
        parts = []
        for k, m in enumerate(marks):
            end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
            body = text[m.end():end].strip().rstrip(";,").strip()
            body = re.sub(r"\s+(and|or)$", "", body)
            if body:
                parts.append((m.group(1), body, stem))
        if len(parts) >= 2:
            return parts
    qs = [s.strip() for s in re.findall(r"[^?]+\?", text)]
    rest = text[sum(len(s) for s in re.findall(r"[^?]+\?", text)):].strip()
    if len(qs) >= 2 and all(len(s.split()) >= 3 for s in qs) and not rest:
        parts = []
        for k, s in enumerate(qs):
            ctx = qs[k - 1] if k > 0 and _FOLLOW_UP.search(s) else ""
            parts.append((str(k + 1), s, ctx))
        return parts
    return [("", text, "")]


# ---- main entry -------------------------------------------------------------------------------

def _is_section_row(row: list[str], layout: Layout) -> str | None:
    filled = [c for c in row if c]
    if len(filled) != 1:
        return None
    value = filled[0]
    if value.endswith(("?", ".")) or len(value.split()) > 6:
        return None
    return re.sub(r"^(section\s+)?[\dA-Z]{1,3}[.)]\s*", "", value, flags=re.I).rstrip(":").strip()


def parse_rows(rows: list[list[str]], fmt: str, sheet: str | None = None) -> ParsedQuestionnaire:
    layout = detect_layout(rows, fmt, sheet)
    items: list[QuestionItem] = []
    section = ""
    for r in range(layout.header_row + 1, len(rows)):
        row = rows[r] + [""] * (layout.n_cols - len(rows[r]))
        sec = _is_section_row(row, layout)
        if sec is not None and not row[layout.question_col].endswith("?"):
            section = sec
            continue
        q = row[layout.question_col]
        if len(q.split()) < 3:
            continue
        if layout.section_col is not None and row[layout.section_col]:
            section = row[layout.section_col]
        ref = row[layout.id_col] if layout.id_col is not None else str(r + 1)
        for label, body, ctx in split_parts(q):
            iid = f"r{r + 1}" + (f".{label}" if label else "")
            items.append(QuestionItem(iid, r, section or "General", ref, q, label, body, ctx))
    if not items:
        raise ParseError("no questions found")
    return ParsedQuestionnaire(layout, items, rows)


def parse_file(data: bytes, filename: str) -> ParsedQuestionnaire:
    fmt = "xlsx" if filename.lower().endswith((".xlsx", ".xlsm")) else "csv"
    if fmt == "csv" and not filename.lower().endswith((".csv", ".txt")):
        raise ParseError(f"unsupported file type: {filename}")
    sheet, rows = read_rows(data, fmt)
    return parse_rows(rows, fmt, sheet)
