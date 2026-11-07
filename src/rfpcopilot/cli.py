"""Command line: generate sample data, answer a questionnaire file, run the eval and the CI gate, serve the API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluate import ClaudeJudge, gate, markdown_table, questionnaire_savings, run_eval


def cmd_gen(a) -> int:
    from .samples import write_samples

    for p in write_samples(Path(a.out)):
        print(p)
    return 0


def cmd_answer(a) -> int:
    from .drafting import make_drafter
    from .export import compliance_matrix, export_file
    from .kb import build_kb
    from .parser import parse_file
    from .pipeline import Pipeline

    path = Path(a.file)
    content = path.read_bytes()
    parsed = parse_file(content, path.name)
    pipe = Pipeline(build_kb()[0], make_drafter(a.drafter))
    items = pipe.process(parsed)
    for it in items:
        d = it["draft"]
        print(f"{it['item_id']:>8}  {it['status']:<13} {d['confidence']:.2f}  {it['text'][:70]}")
    out = Path(a.out or path.with_name(path.stem + "-answered" + path.suffix))
    out.write_bytes(export_file(content, parsed.layout.fmt, parsed.layout.to_dict(), items, include_drafts=True))
    m = compliance_matrix(items, include_drafts=True)
    print(json.dumps({"total": m["total"], "status": m["status"]}))
    print(f"wrote {out}")
    return 0


def cmd_eval(a) -> int:
    judge = ClaudeJudge() if a.judge == "claude" else None
    modes = ["bm25", "hybrid"] if a.compare else [a.mode]
    reports = [run_eval(m, judge=judge) for m in modes]
    table = markdown_table(reports)
    rows = questionnaire_savings()
    table += ("\n| Sample questionnaire | Parts | Auto-approved | Needs review | SME queue | Minutes saved |\n"
              "|---|---:|---:|---:|---:|---:|\n")
    table += "".join(f"| {r['file']} | {r['parts']} | {r['auto_approved']} | {r['needs_review']} | {r['sme']} | "
                     f"{r['minutes_saved']} |\n" for r in rows)
    print(table)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps([{**r.row(), "failures": r.failures} for r in reports], indent=1))
    if a.summary:
        with open(a.summary, "a") as f:
            f.write("## RFP Copilot eval\n\n" + table + "\n")
    if a.gate:
        target = reports[-1]
        problems = gate(target, a.max_outdated, a.min_abstention, a.min_recall)
        for p in problems:
            print(f"GATE FAIL: {p}", file=sys.stderr)
        if problems:
            return 1
        print(f"gate passed for {target.mode}")
    return 0


def cmd_serve(a) -> int:  # pragma: no cover - runs a server
    import uvicorn

    from .api import create_app

    uvicorn.run(create_app(), host=a.host, port=a.port, log_level="warning")
    return 0


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="rfpcopilot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen", help="write the knowledge base, sample questionnaires, and eval set")
    g.add_argument("--out", default="data")
    g.set_defaults(fn=cmd_gen)
    an = sub.add_parser("answer", help="answer a questionnaire file and write the filled copy")
    an.add_argument("file")
    an.add_argument("--out")
    an.add_argument("--drafter", default="extractive", choices=["extractive", "claude"])
    an.set_defaults(fn=cmd_answer)
    e = sub.add_parser("eval", help="run the labeled eval")
    e.add_argument("--mode", default="hybrid", choices=["bm25", "hybrid"])
    e.add_argument("--compare", action="store_true", help="bm25 vs hybrid side by side")
    e.add_argument("--judge", default="facts", choices=["facts", "claude"])
    e.add_argument("--gate", action="store_true")
    e.add_argument("--max-outdated", type=float, default=0.02)
    e.add_argument("--min-abstention", type=float, default=0.8)
    e.add_argument("--min-recall", type=float, default=0.9)
    e.add_argument("--out")
    e.add_argument("--summary", help="append the table to this file (for $GITHUB_STEP_SUMMARY)")
    e.set_defaults(fn=cmd_eval)
    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8822)
    s.set_defaults(fn=cmd_serve)
    a = ap.parse_args(argv)
    sys.exit(a.fn(a))
