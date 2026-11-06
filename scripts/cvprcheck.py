"""Shared helpers for the CVPR submission checks (Python standard library only).

Findings are plain dicts: {"rule": "F2", "status": "PASS|WARN|FAIL|INFO|MANUAL", "title": str, "evidence": [str]}.
"""
import hashlib
import json
import re
import subprocess
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
USER_AGENT = "cvpr-submission-check/1.0 (+https://github.com/yuangao-tum/cvpr-submission-check)"
STATUS_ORDER = {"FAIL": 0, "WARN": 1, "MANUAL": 2, "INFO": 3, "PASS": 4}


def finding(rule, status, title, evidence=None):
    return {"rule": rule, "status": status, "title": title, "evidence": list(evidence or [])}


def load_sources():
    return json.loads((ROOT / "references" / "sources.json").read_text())


def term_re(term):
    """Case-insensitive pattern for an identity term, with word boundaries where the term starts/ends with a word char."""
    a = r"\b" if re.match(r"\w", term) else ""
    b = r"\b" if re.search(r"\w$", term) else ""
    return re.compile(a + re.escape(term) + b, re.I)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- LaTeX sources

def strip_comments(text):
    """Remove LaTeX comments (unescaped %) line by line, keeping line numbers."""
    out = []
    for line in text.split("\n"):
        m = re.search(r"(?<!\\)%", line)
        out.append(line[: m.start()] if m else line)
    return "\n".join(out)


def expand_inputs(main_tex, _seen=None):
    """Return [(file, line_no, line)] for the document in reading order, following \\input / \\include.
    Comments are stripped; files that do not exist are skipped (reported by the caller via 'missing')."""
    main_tex = Path(main_tex)
    base = main_tex.parent
    seen = _seen if _seen is not None else set()
    rows, missing = [], []

    def walk(path):
        path = path if path.suffix else path.with_suffix(".tex")
        if not path.exists():
            missing.append(str(path))
            return
        if path.resolve() in seen:
            return
        seen.add(path.resolve())
        for i, line in enumerate(strip_comments(path.read_text(errors="replace")).split("\n"), 1):
            parts = re.split(r"(\\(?:input|include)\s*\{[^}]+\})", line)
            for part in parts:
                m = re.match(r"\\(?:input|include)\s*\{([^}]+)\}", part)
                if m:
                    rows.append((str(path.relative_to(base) if path.is_relative_to(base) else path), i, part))
                    walk(base / m.group(1).strip())
                elif part.strip():
                    rows.append((str(path.relative_to(base) if path.is_relative_to(base) else path), i, part))

    walk(main_tex)
    return rows, missing


# ---------------------------------------------------------------- BibTeX

def parse_bib(text):
    """Minimal BibTeX parser: returns {key: {"_type": type, field: value, ...}} with raw (LaTeX) values."""
    entries = {}
    i, n = 0, len(text)
    while True:
        m = re.compile(r"@(\w+)\s*([{(])", re.S).search(text, i)
        if not m:
            break
        etype = m.group(1).lower()
        open_ch = m.group(2)
        close_ch = "}" if open_ch == "{" else ")"
        j = m.end()
        depth, k = 1, j
        while k < n and depth:
            c = text[k]
            if c == "{" or (c == open_ch and open_ch == "("):
                depth += 1
            elif c == "}" or (c == close_ch and close_ch == ")"):
                depth -= 1
            k += 1
        body = text[j: k - 1]
        i = k
        if etype in ("comment", "preamble", "string"):
            continue
        key, _, rest = body.partition(",")
        fields = {"_type": etype}
        p = 0
        while p < len(rest):
            fm = re.compile(r"\s*([\w\-:.]+)\s*=\s*", re.S).match(rest, p)
            if not fm:
                break
            name = fm.group(1).lower()
            p = fm.end()
            val, p = _read_value(rest, p)
            fields[name] = val
            cm = re.compile(r"\s*,", re.S).match(rest, p)
            p = cm.end() if cm else p + 1
        entries[key.strip()] = fields
    return entries


def _read_value(s, p):
    parts = []
    while p < len(s):
        while p < len(s) and s[p].isspace():
            p += 1
        if p >= len(s):
            break
        c = s[p]
        if c == "{":
            depth, q = 1, p + 1
            while q < len(s) and depth:
                depth += {"{": 1, "}": -1}.get(s[q], 0)
                q += 1
            parts.append(s[p + 1: q - 1])
            p = q
        elif c == '"':
            q = p + 1
            depth = 0
            while q < len(s) and not (s[q] == '"' and depth == 0):
                depth += {"{": 1, "}": -1}.get(s[q], 0)
                q += 1
            parts.append(s[p + 1: q])
            p = q + 1
        else:
            m = re.compile(r"[^,#\s}]+").match(s, p)
            parts.append(m.group(0) if m else "")
            p = m.end() if m else p + 1
        m = re.compile(r"\s*#\s*").match(s, p)
        if m:
            p = m.end()
            continue
        break
    return " ".join(parts).strip(), p


_ACCENT = re.compile(r"\\[`'^\"~=.uvHcdbtkr]\s*\{?\s*\\?([A-Za-z])\}?")
_SPECIAL = {r"\ss": "ss", r"\o": "o", r"\O": "O", r"\ae": "ae", r"\AE": "AE", r"\aa": "a", r"\AA": "A",
            r"\l": "l", r"\L": "L", r"\i": "i", r"\&": "&", r"\%": "%", r"\_": "_", r"\textendash": "-",
            r"\textemdash": "-", "~": " ", "--": "-"}


def delatex(s):
    s = _ACCENT.sub(r"\1", s or "")
    for a, b in _SPECIAL.items():
        s = s.replace(a, b)
    s = re.sub(r"\\(?:emph|textit|textbf|textsc|texttt|textrm|mathrm|mbox|text)\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\$([^$]*)\$", r"\1", s)
    s = re.sub(r"\\[A-Za-z]+\s*", " ", s)
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


def norm_text(s):
    s = unicodedata.normalize("NFKD", delatex(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def bib_authors(raw):
    """Split a BibTeX author field into display names (brace-aware ' and ')."""
    names, depth, cur, toks = [], 0, "", re.split(r"(\{|\}|\s+and\s+)", raw or "")
    for t in toks:
        if t == "{":
            depth += 1
        elif t == "}":
            depth -= 1
        if re.fullmatch(r"\s+and\s+", t or "") and depth == 0:
            names.append(cur.strip())
            cur = ""
        else:
            cur += t
    if cur.strip():
        names.append(cur.strip())
    return [n for n in names if n and n.lower() != "others"]


def surname(name):
    raw = name.strip()
    if raw.startswith("{") and raw.endswith("}"):  # corporate author
        return norm_text(raw)
    n = delatex(raw)
    if "," in n:
        return norm_text(n.split(",")[0])
    parts = n.split()
    return norm_text(parts[-1]) if parts else ""


def title_similarity(a, b):
    import difflib
    a, b = norm_text(a), norm_text(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    r = difflib.SequenceMatcher(None, a, b).ratio()
    # A bib title may omit or add a subtitle: accept containment of the main title.
    short, long_ = sorted((a, b), key=len)
    if len(short) >= 20 and long_.startswith(short):
        r = max(r, 0.95)
    return r


# ---------------------------------------------------------------- HTTP

class Http:
    """GET with a per-host minimum interval, retries on 429/5xx, and an on-disk JSON cache."""

    def __init__(self, cache_path=None, intervals=None):
        self.cache_path = Path(cache_path) if cache_path else None
        self.cache = json.loads(self.cache_path.read_text()) if self.cache_path and self.cache_path.exists() else {}
        self.intervals = intervals or {}
        self.last = {}
        self.failed = {}  # host -> reason, for requests that never succeeded (rate limit, budget, network)

    def get(self, url, retries=4):
        ck = re.sub(r"[&?](api_key|mailto)=[^&]*", "", url)  # never store credentials in the cache file
        if ck in self.cache:
            return self.cache[ck]
        host = urllib.parse.urlparse(url).netloc
        for attempt in range(retries):
            wait = self.intervals.get(host, 1.0) - (time.time() - self.last.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            self.last[host] = time.time()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=30) as r:
                    body = r.read().decode("utf-8", errors="replace")
                self.cache[ck] = body
                self.failed.pop(host, None)
                self._save()
                return body
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    msg = e.read().decode("utf-8", errors="replace")[:200] if hasattr(e, "read") else ""
                    if re.search(r"budget|quota|api key", msg, re.I):  # daily budget used up: retrying will not help
                        self.failed[host] = "429 " + msg[:120]
                        return None
                if e.code in (429, 500, 502, 503, 504):
                    self.failed[host] = f"HTTP {e.code}"
                    time.sleep(5 * (attempt + 1))
                    continue
                if e.code == 404:
                    self.cache[ck] = ""
                    self._save()
                    return ""
                raise
            except (urllib.error.URLError, TimeoutError) as e:
                self.failed[host] = f"network: {e}"[:120]
                time.sleep(5 * (attempt + 1))
        return None  # failure: not cached, so a re-run retries

    def _save(self):
        if self.cache_path:
            self.cache_path.write_text(json.dumps(self.cache))


# ---------------------------------------------------------------- PDF (poppler)

def pdf_pages(pdf, layout=False):
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
    n = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    pages = []
    for p in range(1, n + 1):
        cmd = ["pdftotext", "-f", str(p), "-l", str(p)] + (["-layout"] if layout else []) + [str(pdf), "-"]
        pages.append(subprocess.run(cmd, capture_output=True, text=True).stdout)
    return info, pages


def report_markdown(findings, title, meta_lines=()):
    order = sorted(findings, key=lambda f: (STATUS_ORDER[f["status"]], f["rule"]))
    counts = {s: sum(f["status"] == s for f in findings) for s in STATUS_ORDER}
    out = [f"# {title}", ""] + list(meta_lines) + [
        "", "Summary: " + ", ".join(f"{k} {v}" for k, v in counts.items()), "",
        "| Status | Rule | Check |", "|---|---|---|"]
    out += [f"| {f['status']} | {f['rule']} | {f['title']} |" for f in order]
    out.append("")
    for f in order:
        if f["evidence"]:
            out.append(f"## {f['status']} {f['rule']}: {f['title']}")
            out += [f"- {e}" for e in f["evidence"][:60]]
            if len(f["evidence"]) > 60:
                out.append(f"- ... {len(f['evidence']) - 60} more")
            out.append("")
    return "\n".join(out) + "\n"
