"""PDF checks (poppler: pdfinfo, pdftotext, pdffonts): page limit (F2), header/paper ID (F1), letter size and fonts (F3/F6),
PDF metadata (A2), identity terms and links in the text (A1/A3), hidden instructions (I3), unresolved references and
placeholders (I4), appended supplement (S1)."""
import re
import subprocess

from cvprcheck import finding, pdf_pages, term_re
from check_tex import INJECTION

NOISE = re.compile(r"^(CVPR|ICCV|ECCV)(\s*#\S*)?$|CONFIDENTIAL REVIEW COPY|^\d{1,4}$|^#?\*+$|^Anonymous \w+ submission$")


def content_lines(page):
    return [l.strip() for l in page.splitlines() if l.strip() and not NOISE.search(l.strip())]


def run(args):
    out = []
    info, pages = pdf_pages(args.pdf)
    n = len(pages)
    heading = lambda p, h: any(l == h for l in content_lines(p))  # noqa: E731
    llm = [i for i, p in enumerate(pages, 1) if heading(p, "LLM Usage Statement")]
    refs = [i for i, p in enumerate(pages, 1) if heading(p, "References")]
    supp = [i for i, p in enumerate(pages, 1) if heading(p, "Supplementary Material") and (not refs or i > refs[0])]
    end_main = (refs[0] if refs else n) if not llm else llm[0]

    # ---- F2 page limit
    ev = [f"{n} pages; LLM Usage Statement heading on page {llm[0] if llm else '-'}; References on page {refs[0] if refs else '-'}"
          + (f"; supplement starts on page {supp[0]}" if supp else "")]
    status = "PASS"
    if not llm:
        status = "FAIL"
        ev.append("no 'LLM Usage Statement' heading found in the PDF text")
    else:
        p = llm[0]
        if p > 9:
            status = "FAIL"
        elif p == 9:
            first = content_lines(pages[8])[:1]
            if first != ["LLM Usage Statement"]:
                status = "FAIL"
                ev.append(f"page 9 starts with main text before the statement: {first}")
            else:
                ev.append("the statement is the first text on page 9: the main text ends on page 8")
        else:
            before = content_lines(pages[p - 1])
            k = before.index("LLM Usage Statement")
            ev.append(f"main text ends on page {p}, just before the statement; last line: \"{before[k - 1][:80] if k else ''}\"")
    out.append(finding("F2", status, "Main text within eight pages (references and LLM statement excluded)", ev))

    # ---- F1 header / paper ID (2027 kit removed the ID)
    p1 = pages[0]
    ev = []
    if re.search(r"Paper ID|Submission\s*#", p1):
        ev.append("page 1 shows a Paper ID or 'Submission #' (2026-or-older cvpr.sty; the 2027 kit removed it)")
    if not re.search(r"Anonymous \w+ submission", p1):
        ev.append("page 1 lacks 'Anonymous ... submission' (review option off?)")
    yr = re.search(r"(CVPR|ICCV|ECCV) (\d{4}) Submission", p1)
    ev.append(f"header: {yr.group(0) if yr else 'no conference header found'}")
    out.append(finding("F1", "FAIL" if len(ev) > 1 or not (yr and yr.group(2) == "2027") else "PASS",
                       "Review header of the 2027 template", ev))

    # ---- F3 page size, F6 fonts
    size = re.search(r"Page size:\s+([\d.]+) x ([\d.]+) pts(?: \((\w+)\))?", info)
    letter = size and abs(float(size.group(1)) - 612) < 1 and abs(float(size.group(2)) - 792) < 1
    out.append(finding("F3", "PASS" if letter else "FAIL", "US letter pages (612 x 792 pt)", [size.group(0) if size else "no page size"]))
    fonts = subprocess.run(["pdffonts", str(args.pdf)], capture_output=True, text=True).stdout.splitlines()[2:]
    not_emb = [l for l in fonts if len(l.split()) >= 5 and re.search(r"\bno\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$", l)]
    t3 = [l for l in fonts if " Type 3 " in l]
    out.append(finding("F6", "WARN" if not_emb else "PASS", "All fonts embedded",
                       [f"not embedded: {l.split()[0]}" for l in not_emb] + [f"Type 3 font (fine for review): {l.split()[0]}" for l in t3[:5]]))

    # ---- A2 metadata
    meta = {k: v.strip() for k, v in re.findall(r"^(Title|Author|Subject|Keywords|Creator|Producer):\s*(.*)$", info, re.M)}
    ev = [f"{k}: {v}" for k, v in meta.items() if v]
    hits = [f"{k} contains '{t}'" for k, v in meta.items() for t in args.identity_terms if term_re(t).search(v)]
    status = "FAIL" if hits else ("WARN" if meta.get("Author") else "PASS")
    out.append(finding("A2", status, "PDF metadata reveals no author", hits + ev))

    # ---- A1 identity terms in the text before the references; A3 links
    body = "\n".join(pages[: (refs[0] - 1 if refs else n)])
    after_refs = "\n".join(pages[(supp[0] - 1):]) if supp else ""
    ev = []
    for t in args.identity_terms:
        for where, txt in (("paper", body), ("supplement", after_refs)):
            for m in term_re(t).finditer(txt):
                ev.append(f"{where}: '{t}' in \"...{txt[max(0, m.start() - 60):m.end() + 60].replace(chr(10), ' ')}...\"")
    emails = sorted(set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", body + after_refs)))
    ev += [f"e-mail address: {e}" for e in emails]
    out.append(finding("A1", "WARN" if ev else "PASS", "No author-identifying text in the PDF (outside the reference list)", ev))
    joined = "\n".join(pages)
    for _ in range(4):  # re-join URLs that the PDF wraps across lines
        joined = re.sub(r"((?:https?://|www\.)\S*[./\-_?=&#])\n(?=\S)", r"\1", joined)
    urls = sorted(set(u.rstrip(".") for u in re.findall(r"(?:https?://|www\.)[^\s)\]}>,;]+", joined)))
    out.append(finding("A3", "WARN" if urls else "PASS", "URLs printed in the PDF (decide each)", urls))

    # ---- I3 instruction-like text in the PDF (catches text hidden by color, which pdftotext still extracts)
    ev = []
    for i, p in enumerate(pages, 1):
        for m in re.finditer(INJECTION, p, re.I):
            ev.append(f"page {i}: \"...{p[max(0, m.start() - 60):m.end() + 60].replace(chr(10), ' ')}...\"")
    out.append(finding("I3", "FAIL" if ev else "PASS", "No reviewer-directed instructions in the PDF text (incl. invisible text)", ev))

    # ---- I4 unresolved references / placeholders in the PDF
    ev = []
    for i, p in enumerate(pages, 1):
        for m in re.finditer(r"\?\?|\[\?\]|\(\?\)|\bTODO\b|\bTBD\b|\bFIXME\b|\bXXX\b" + ("|" + "|".join(args.placeholder) if args.placeholder else ""), p):
            ev.append(f"page {i}: \"...{p[max(0, m.start() - 50):m.end() + 50].replace(chr(10), ' ')}...\"")
    out.append(finding("I4", "FAIL" if ev else "PASS", "No unresolved references (??, [?]) or placeholders in the PDF", ev))

    # ---- S1
    if supp:
        out.append(finding("S1", "INFO", f"Supplement appended (pages {supp[0]}-{n}): upload pages 1-{supp[0] - 1} as the paper "
                           "and the rest as the supplement", [f"main paper incl. references: pages 1-{supp[0] - 1}"]))
    return out, {"pages": n, "llm_page": llm[0] if llm else None, "refs_page": refs[0] if refs else None,
                 "supp_page": supp[0] if supp else None, "main_end_page": end_main}
