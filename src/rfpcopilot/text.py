"""Text utilities: tokenizing, BM25, fuzzy question similarity, and fact extraction for conflict checks."""

from __future__ import annotations

import math
import re
from collections import Counter
from difflib import SequenceMatcher

STOPWORDS = set("""
a an the and or of to in on for with by at from as is are was were be been being do does did you your yours we our
ours us it its this that these those there their they them what which who whom how when where why can could would
should will shall may might must please provide describe explain confirm detail details state list any all each
if so else than then into about over under have has had not no yes also such other per via vendor company
organization organisation corvane insight platform service product solution offering applicable i ii iii
use used using apply applies through get gets much many before after ever first keep major possible example
run against own inside support supported offer offered available allow allowed ensure make take way kind kinds
different give high level overview actually any anything whether which while like out up down there here
""".split())

# Common questionnaire paraphrases mapped onto the wording the library uses.
SYNONYMS = {
    "frequently": "often", "frequency": "often", "cadence": "often", "periodically": "often",
    "terminates": "termination", "terminate": "termination", "leave": "termination", "copy": "export",
    "phone": "mobile", "handheld": "mobile", "sign-ins": "login", "signin": "login", "logins": "login",
    "notice": "announced", "remediated": "remediation", "fixed": "remediation", "exposed": "breach",
    "compromise": "breach", "compromised": "breach", "recertified": "reviewed", "kept": "retained",
    "keep": "retain", "fast": "quickly", "soon": "quickly", "prevent": "isolated", "segregate": "isolated",
    "commitment": "commits", "outage": "availability", "uptime": "uptime availability",
}

# Expanding acronyms lets a question that says "SSO" match an answer that says "single sign-on".
# A real deployment would use embeddings here. A short domain glossary covers most RFP vocabulary.
ACRONYMS = {
    "sso": "single sign on", "idp": "identity provider", "mfa": "multi factor authentication",
    "2fa": "multi factor authentication", "dpa": "data processing agreement", "baa": "business associate agreement",
    "rpo": "recovery point objective", "rto": "recovery time objective", "dr": "disaster recovery",
    "bcp": "business continuity plan", "sbom": "software bill of materials", "siem": "siem security event",
    "waf": "web application firewall", "ddos": "ddos denial service", "pentest": "penetration test",
    "nda": "confidentiality agreement", "byok": "byok customer managed keys", "sla": "sla service level",
    "soc": "security operations soc", "vpat": "accessibility wcag", "phi": "protected health hipaa",
    "pii": "personal data", "sdlc": "secure development lifecycle", "scim": "scim provisioning",
}

_TOKEN = re.compile(r"[a-z0-9]+(?:[.:][0-9]+)*")


def stem(word: str) -> str:
    for suffix in ("ations", "ation", "ings", "ing", "ies", "ied", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            base = word[: -len(suffix)] + ("y" if suffix in ("ies", "ied") else "")
            if suffix in ("ed", "ing", "ings") and len(base) > 3 and base[-1] == base[-2] and base[-1] not in "ls":
                base = base[:-1]  # scanned -> scan
            return base
    return word


def tokenize(text: str, expand: bool = True) -> list[str]:
    out: list[str] = []
    for raw in _TOKEN.findall(text.lower()):
        if expand and raw in ACRONYMS:
            words = ACRONYMS[raw].split()
        elif expand and raw in SYNONYMS:
            words = SYNONYMS[raw].split()
        else:
            words = [raw]
        for w in words:
            if w not in STOPWORDS and len(w) > 1:
                out.append(stem(w))
    return out


class BM25:
    """Okapi BM25 over a list of token lists."""

    def __init__(self, docs: list[list[str]], k1: float = 1.4, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.n = len(docs)
        self.avgdl = sum(len(d) for d in docs) / max(self.n, 1)
        self.tf = [Counter(d) for d in docs]
        df: Counter[str] = Counter()
        for d in docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def score(self, query: list[str], i: int) -> float:
        tf, dl, s = self.tf[i], len(self.docs[i]), 0.0
        for t in set(query):
            if t not in tf:
                continue
            f = tf[t]
            s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return s

    def scores(self, query: list[str]) -> list[float]:
        return [self.score(query, i) for i in range(self.n)]


def question_similarity(a: str, b: str) -> float:
    """Fuzzy similarity of two questions in [0, 1]: token overlap blended with character sequence match."""
    ta, tb = set(tokenize(a)), set(tokenize(b))
    if not ta or not tb:
        return 0.0
    overlap = len(ta & tb) / len(ta | tb)
    containment = len(ta & tb) / min(len(ta), len(tb))
    seq = SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    return round(0.4 * overlap + 0.3 * containment + 0.3 * seq, 4)


def normalize_question(q: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", q.lower()).split())


# ---- facts for conflict detection -------------------------------------------------------------

_NUM_UNIT = re.compile(r"(?<![\w.:-])(\d+(?:,\d{3})*(?:\.\d+)?)\s*(%|[a-z]+)")
_VERSIONED = [
    (re.compile(r"\btls\s*(\d\.\d)"), "tls"),
    (re.compile(r"\baes-?(\d{3})"), "aes"),
    (re.compile(r"\btype\s+(ii|i)\b"), "soc2-type"),
    (re.compile(r"27001:(\d{4})"), "iso27001"),
    (re.compile(r"\bnet\s+(\d+)"), "net-days"),
    (re.compile(r"\bfips\s*140-(\d)"), "fips"),
]
_SKIP_UNITS = STOPWORDS | {"between", "until", "after", "before", "within", "x"}


def numbers_in(text: str) -> set[str]:
    return {m.group(1).replace(",", "") for m in _NUM_UNIT.finditer(text.lower())}


def extract_facts(text: str) -> dict[str, set[str]]:
    """Comparable facts: {unit: {values}}, plus versioned identifiers and the yes/no polarity."""
    low = text.lower()
    facts: dict[str, set[str]] = {}
    for m in _NUM_UNIT.finditer(low):
        value, unit = m.group(1).replace(",", ""), m.group(2)
        if unit in _SKIP_UNITS:
            continue
        unit = unit if unit == "%" else stem(unit.rstrip("s") if len(unit) > 3 else unit)
        facts.setdefault(unit, set()).add(value)
    for pattern, name in _VERSIONED:
        for v in pattern.findall(low):
            facts.setdefault(name, set()).add(v)
    first = low.strip().split(".")[0].strip() if low.strip() else ""
    if first in ("yes", "no", "partial"):
        facts["polarity"] = {first}
    return facts


def facts_conflict(a: dict[str, set[str]], b: dict[str, set[str]]) -> list[str]:
    """Units where the two fact sets disagree. Equal or nested value sets are consistent
    (a short answer may state only one of the numbers a policy gives)."""
    out = []
    for unit in sorted(set(a) & set(b)):
        va, vb = a[unit], b[unit]
        if not (va <= vb or vb <= va):
            out.append(f"{unit}: {', '.join(sorted(va))} vs {', '.join(sorted(vb))}")
    return out


_CITE = re.compile(r"\[([A-Za-z0-9][A-Za-z0-9_.#-]*)\]")


def strip_citations(text: str) -> str:
    return re.sub(r"\s+([.,;])", r"\1", _CITE.sub("", text)).replace("  ", " ").strip()


def find_citations(text: str) -> list[str]:
    seen: list[str] = []
    for c in _CITE.findall(text):
        if c not in seen:
            seen.append(c)
    return seen


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text) if s.strip()]
