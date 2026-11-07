"""Synthetic incoming questionnaires (CSV and XLSX) and the labeled eval set.

The customers are made up. Each file has the mess real questionnaires have: title rows above the header,
merged section rows, a yes/no column next to an explanation column, multi-part questions, wording that differs
from the answer library, and a few questions the knowledge base cannot answer.
"""

from __future__ import annotations

import csv
import io
import json
import random
from pathlib import Path

from .kb import build_kb
from .kbdata import TOPICS, UNANSWERABLE

TOPIC = {t.key: t for t in TOPICS}


def _q(key: str, rng: random.Random, library_share: float = 0.4) -> str:
    t = TOPIC[key]
    if rng.random() < library_share:
        return rng.choice(t.library_questions)
    return t.eval_question


TALLIS = [  # Tallis Freight, security questionnaire, XLSX with merged section rows and Yes/No + Explanation
    ("1. Governance and Compliance", ["soc2", "iso27001", "gdpr", "pentest", "audit-rights"]),
    ("2. Identity and Access", ["sso", "mfa", "privileged-access", "access-review", "MULTI:a) Do you support SCIM? "
                                "b) What is the idle session timeout?"]),
    ("3. Data Security", ["enc-rest", "enc-transit", "byok", "retention-termination", "ai-training", "UNANS:3"]),
    ("4. Resilience", ["backups", "rpo-rto", "dr-test", "MULTI:Do you have an incident response plan? If so, how "
                       "quickly will you notify us of a breach?"]),
    ("5. Third Parties", ["subprocessors", "vendor-risk", "UNANS:0"]),
]

MERROW = [  # Merrow Health Partners, RFP, CSV with a category column
    ("Security", ["hipaa", "enc-rest", "malware", "monitoring", "breach-history", "UNANS:1"]),
    ("Privacy", ["data-residency", "deletion-request", "offshore", "test-data"]),
    ("Service Levels", ["sla-uptime", "support-hours", "response-times", "maintenance", "status-page"]),
    ("Technical", ["api", "api-rate-limits", "integrations", "mobile", "accessibility",
                   "MULTI:(i) Which browsers are supported? (ii) Do you provide a sandbox environment?"]),
    ("Commercial", ["pricing-model", "payment-terms", "price-increase", "liability", "UNANS:2"]),
]

OKAFOR = [  # Okafor Retail Group, vendor due diligence, XLSX with header on row 4 and Y/N/Partial column
    ("Security Operations", ["vuln-scanning", "patch-sla", "bug-bounty", "audit-log", "log-retention"]),
    ("Platform", ["hosting", "multi-tenancy", "single-tenant", "network-security", "ddos", "os-hardening",
                  "MULTI:Regarding the architecture: a) What are the main components of the platform? b) Do you "
                  "use a web application firewall? c) Are servers hardened?"]),
    ("People", ["background-checks", "security-training", "confidentiality", "UNANS:7"]),
    ("Engineering", ["code-review", "change-mgmt", "sbom", "UNANS:4"]),
]


def _rows(spec, rng) -> list[tuple[str, str]]:
    out = []
    for section, keys in spec:
        out.append((section, None))
        for k in keys:
            if k.startswith("MULTI:"):
                out.append((section, k[6:]))
            elif k.startswith("UNANS:"):
                out.append((section, UNANSWERABLE[int(k[6:])]))
            else:
                out.append((section, _q(k, rng)))
    return out


def tallis_xlsx(rng: random.Random) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Security Questionnaire"
    ws["A1"] = "Tallis Freight Vendor Security Assessment"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = "Vendor name: Corvane"
    ws["A3"] = "Answer every question. Use the Explanation column for detail. Return by the due date in the RFP."
    ws.merge_cells("A1:D1")
    ws.merge_cells("A3:D3")
    header = ["#", "Question", "Yes/No", "Explanation"]
    ws.append([])
    ws.append(header)
    for c in ws[5]:
        c.font = Font(bold=True)
    n = 0
    fill = PatternFill("solid", fgColor="DDE7F0")
    for section, q in _rows(TALLIS, rng):
        if q is None:
            ws.append([section])
            r = ws.max_row
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
            ws.cell(r, 1).font = Font(bold=True)
            ws.cell(r, 1).fill = fill
            continue
        n += 1
        ws.append([f"{n}", q, None, None])
        ws.cell(ws.max_row, 2).alignment = Alignment(wrap_text=True)
    for col, w in zip("ABCD", (6, 70, 10, 70), strict=True):
        ws.column_dimensions[col].width = w
    info = wb.create_sheet("Instructions")
    info["A1"] = "Contact the Tallis Freight procurement team with questions about this assessment."
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def merrow_csv(rng: random.Random) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Merrow Health Partners - Request for Proposal: Analytics Platform"])
    w.writerow(["Section 4: Vendor Requirements. Respond in the Vendor Response column."])
    w.writerow(["Requirement ID", "Category", "Requirement", "Vendor Response"])
    n = 0
    for section, q in _rows(MERROW, rng):
        if q is None:
            continue
        n += 1
        w.writerow([f"MHP-{n:03d}", section, q, ""])
    return buf.getvalue().encode()


def okafor_xlsx(rng: random.Random) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Due Diligence"
    ws["A1"] = "Okafor Retail Group"
    ws["A2"] = "Third-Party Due Diligence Questionnaire v3"
    ws.append([])
    ws.append(["Ref", "Domain", "Control Question", "Response (Y/N/Partial)", "Comments"])
    for c in ws[4]:
        c.font = Font(bold=True)
    n = 0
    for section, q in _rows(OKAFOR, rng):
        if q is None:
            continue
        n += 1
        ws.append([f"DD-{n:02d}", section, q, None, None])
    for col, w in zip("ABCDE", (8, 20, 70, 14, 60), strict=True):
        ws.column_dimensions[col].width = w
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


SAMPLES = {
    "tallis-freight-security.xlsx": tallis_xlsx,
    "merrow-health-rfp.csv": merrow_csv,
    "okafor-retail-due-diligence.xlsx": okafor_xlsx,
}


def sample_bytes(name: str) -> bytes:
    return SAMPLES[name](random.Random(f"{name}-11"))


def build_eval_set(seed: int = 7) -> dict:
    """Labeled questions: 70 answerable (held-out phrasing) and 10 unanswerable, with gold facts and sources."""
    kb, truth = build_kb(seed)
    skip = [t.key for t in TOPICS if not t.old_answer and not t.contra_answer][::6][:10]
    items = []
    for t in TOPICS:
        if t.key in skip:
            continue
        gold = sorted(truth["current"][t.key]) + [truth["doc_chunk"][t.key]]
        items.append({"id": f"ev-{t.key}", "question": t.eval_question, "section": t.section,
                      "answerable": True, "gold_facts": list(t.facts), "gold_compliance": t.compliance,
                      "gold_sources": gold, "gold_answer": t.answer})
    for i, q in enumerate(UNANSWERABLE):
        items.append({"id": f"ev-unanswerable-{i}", "question": q, "section": "", "answerable": False,
                      "gold_facts": [], "gold_compliance": "unanswered", "gold_sources": [], "gold_answer": ""})
    return {"seed": seed, "outdated_ids": truth["outdated"], "contradictory_ids": truth["contradictory"],
            "items": items}


def write_samples(root: Path) -> list[Path]:
    from .kb import save_kb

    kb, _ = build_kb()
    save_kb(kb, root / "kb")
    out = []
    (root / "questionnaires").mkdir(parents=True, exist_ok=True)
    for name in SAMPLES:
        p = root / "questionnaires" / name
        p.write_bytes(sample_bytes(name))
        out.append(p)
    (root / "eval").mkdir(parents=True, exist_ok=True)
    p = root / "eval" / "eval_set.json"
    p.write_text(json.dumps(build_eval_set(), indent=1) + "\n")
    out.append(p)
    return out
