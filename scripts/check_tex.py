"""LaTeX source checks: template (F1), layout changes (F3), LLM Usage Statement (F4/F5), anonymity hints (A1),
links (A3/A4), prompt-injection patterns (I3), placeholders (I4), supplement (S1)."""
import re
from pathlib import Path

from cvprcheck import expand_inputs, finding, load_sources, parse_bib, sha256_file, term_re

# Tools an LLM statement would name; models used as research objects also match, which is fine for this heuristic.
TOOL_NAMES = r"ChatGPT|GPT-?\d|GPT-4o|\bo[134](?:-mini)?\b|Claude|Gemini|Copilot|Codex|Cursor|Grammarly|DeepL|Llama|" \
             r"Mistral|Qwen|DeepSeek|Kimi|Writefull|Perplexity|Bard|Windsurf|Overleaf|gpt-oss|Phi-?\d|Gemma"
USE_WORDS = r"assist|edit|grammar|polish|proofread|rewrit|translat|writ|draft|cod(e|ing)|script|ideation|figure"
LAYOUT = [
    (r"\\usepackage(\[[^\]]*\])?\{geometry\}|\\newgeometry", "geometry package (margins)"),
    (r"\\(setlength|addtolength)\s*\{?\\(textheight|textwidth|topmargin|oddsidemargin|evensidemargin|columnsep|"
     r"headheight|headsep|footskip|voffset|hoffset)\b", "page-layout length"),
    (r"\\linespread|\\renewcommand\s*\{?\\baselinestretch|\\setstretch", "line spacing"),
    (r"\\(renewcommand|let)\s*\{?\\(normalsize|small|footnotesize)\b", "base font size redefined"),
    (r"\\fontsize\s*\{", "explicit \\fontsize"),
]
INJECTION = r"ignore (all |any )?(previous|prior|above) instructions|positive review|give (this|the) paper|" \
            r"as an? (ai|language model|llm)|accept this paper|reviewer[s]? (must|should) (rate|score|accept)"
PLACEHOLDER = r"\\todo\b|\\TODO\b|\bTODO\b|\bTBD\b|\bFIXME\b|\bXXX\b|\[CITATION NEEDED\]|\?\?\?"


def ctx(line, m, width=70):
    a, b = max(0, m.start() - width), m.end() + width
    return ("..." if a else "") + line[a:b].strip() + ("..." if b < len(line) else "")


SELF_CITE = (r"\b(our|my)\s+(own\s+)?(previous|prior|earlier)\s+(work|paper|study|method|benchmark|dataset)s?|"
             r"\bin\s+our\s+(previous|prior|earlier)\b|\bwe\s+(previously|earlier)\s+(proposed|introduced|showed|presented)|"
             r"\bas\s+we\s+(show|showed|demonstrated|reported)\s+in\s*~?\\cite")


def run(args):
    out = []
    main = Path(args.main).resolve()
    paper = main.parent
    rows, missing = expand_inputs(main)
    doc = [(f, i, l) for f, i, l in rows]
    text = "\n".join(l for _, _, l in doc)
    src = load_sources()
    kit = src["author_kit"]

    # ---- F1 template
    ev, bad = [], False
    sty = paper / "cvpr.sty"
    if sty.exists():
        h = sha256_file(sty)
        prov = re.search(r"\\ProvidesPackage\{cvpr\}\[([^\]]*)\]", sty.read_text(errors="replace"))
        ev.append(f"cvpr.sty: {prov.group(1) if prov else 'no ProvidesPackage line'}; sha256 {h[:12]}... "
                  f"({'= 2027 kit' if h == kit['sha256_cvpr_sty'] else 'differs from the 2027 kit ' + kit['sha256_cvpr_sty'][:12] + '...'})")
        bad |= h != kit["sha256_cvpr_sty"]
    else:
        ev.append("cvpr.sty not found next to the main file")
        bad = True
    if not re.search(r"\\usepackage\[review\]\{cvpr\}", text):
        ev.append("\\usepackage[review]{cvpr} is not active (needed for the submission)")
        bad = True
    y = re.search(r"\\def\\confYear\{(\d{4})\}", text)
    ev.append(f"\\confYear = {y.group(1) if y else 'not set'}")
    bad |= not (y and y.group(1) == "2027")
    if not re.search(r"\\documentclass\[10pt,\s*twocolumn,\s*letterpaper\]\{article\}", text):
        ev.append("\\documentclass is not [10pt,twocolumn,letterpaper]{article}")
        bad = True
    out.append(finding("F1", "FAIL" if bad else "PASS", "Official 2027 template in review mode", ev))
    if missing:
        out.append(finding("F1", "WARN", "Some \\input files were not found", missing))

    # ---- F3 layout changes
    ev = [f"{f}:{i}: {ctx(l, m, 50)} ({why})" for f, i, l in doc for pat, why in LAYOUT for m in [re.search(pat, l)]
          if m and not (why == "explicit \\fontsize" and re.search(r"font\s*=|\\node|tikz", l))]
    neg = sum(len(re.findall(r"\\vspace\*?\s*\{\s*-", l)) for _, _, l in doc)
    ev.append(f"negative \\vspace: {neg} (not forbidden as such; heavy use can read as squeezing the format)")
    out.append(finding("F3", "WARN" if len(ev) > 1 else "PASS", "No altered margins, line spacing or base font size", ev))

    # ---- F4/F5 LLM Usage Statement
    idx = [k for k, (_, _, l) in enumerate(doc) if re.search(r"\\section\*?\s*\{\s*LLM Usage Statement\s*\}", l)]
    bib = [k for k, (_, _, l) in enumerate(doc) if re.search(r"\\bibliography\{|\\printbibliography|\\begin\{thebibliography\}", l)]
    if not idx:
        out.append(finding("F4", "FAIL", "Section titled 'LLM Usage Statement' after the main text, before the references",
                           ["no \\section{LLM Usage Statement} or \\section*{...} found"]))
    else:
        k = idx[0]
        ok = bool(bib) and k < bib[0]
        after = [l.strip() for _, _, l in doc[k + 1:(bib[0] if bib else len(doc))]]
        later_sections = [l for l in after if re.match(r"\\(sub)*section", l)]
        ev = [f"heading at {doc[k][0]}:{doc[k][1]}", f"bibliography {'after' if ok else 'NOT after'} the statement"]
        if later_sections:
            ev.append(f"sections between the statement and the references: {later_sections[:3]}")
        out.append(finding("F4", "PASS" if ok and not later_sections else "FAIL",
                           "Section titled 'LLM Usage Statement' after the main text, before the references", ev))
        stmt = " ".join(after)
        clean = re.sub(r"\\[cC]?ref\{[^}]*\}|\\cite\w*\{[^}]*\}", "", stmt)
        sents = re.split(r"(?<=[.;])\s+", re.sub(r"\s*\(\s*\)", "", clean))
        vague = [s.strip() for s in sents if re.search(USE_WORDS, s, re.I) and re.search(r"assistant|LLM|language model|AI tool|generative", s, re.I)
                 and not re.search(TOOL_NAMES, s)]
        none_used = "No LLMs or generative AI tools were used in this work" in stmt
        if none_used:
            out.append(finding("F5", "PASS", "LLM statement names tools, parts affected and extent", ["states that none were used"]))
        else:
            out.append(finding("F5", "WARN" if vague else "MANUAL", "LLM statement names tools, parts affected and extent",
                               ([f"names no tool: \"{s[:220]}\"" for s in vague] or ["every use sentence names a tool; check parts and extent by hand"])
                               + ["rule: name the tool(s), the parts affected, and the nature and extent of use; "
                                  "a statement that leaves out significant information may lead to desk rejection"]))

    # ---- A1 anonymity hints in the sources
    ev = []
    for f, i, l in doc:
        if re.search(r"\\section\*?\{\s*Acknowledge?ments?\s*\}|\\(begin\{ack|acknowledgments)", l, re.I):
            ev.append(f"{f}:{i}: acknowledgments in the review version: {l.strip()[:100]}")
        m = re.search(SELF_CITE, l, re.I)
        if m:
            ev.append(f"{f}:{i}: possible first-person self-citation: {ctx(l, m)}")
    for name in args.identity_terms:
        for f, i, l in doc:
            m = term_re(name).search(l)
            if m and not re.search(r"\\author", l):
                ev.append(f"{f}:{i}: identity term '{name}': {ctx(l, m)}")
    out.append(finding("A1", "WARN" if ev else "PASS", "No author-identifying text in the sources (excluding \\author and the bibliography)", ev))

    # ---- A3/A4 links (sources and bib)
    ev = []
    for f, i, l in doc:
        for m in re.finditer(r"\\(url|href)\s*\{([^}]*)\}|https?://[^\s}{\\]+", l):
            ev.append(f"{f}:{i}: {m.group(0)[:140]}")
    for bibf in args.bib:
        for key, e in parse_bib(Path(bibf).read_text(errors="replace")).items():
            for fld in ("url", "howpublished", "note", "doi"):
                v = e.get(fld, "")
                if re.search(r"https?://|www\.|\\url", v):
                    ev.append(f"{Path(bibf).name}:{key}.{fld}: {v[:140]}")
    code = [e for e in ev if re.search(r"github|gitlab|huggingface|bitbucket|anonymous\.4open|drive\.google|dropbox", e, re.I)]
    out.append(finding("A3", "WARN" if ev else "PASS", "External links (decide each: allowed only if it neither expands content nor identifies authors)", ev))
    if code:
        out.append(finding("A4", "WARN", "Links to code, data or file hosts (own code base may not be cited)", code))

    # ---- I3 prompt injection / hidden text
    ev = []
    for f, i, l in doc:
        if re.search(r"\\(textcolor|color)\s*\{\s*white\s*\}|\\color\[[^\]]*\]\{[^}]*\}\{1,\s*1,\s*1\}|\\fontsize\s*\{\s*0*[0-2](\.\d+)?\s*(pt)?\s*\}|"
                     r"\\resizebox\s*\{\s*0", l):
            ev.append(f"{f}:{i}: invisible-text construct: {l.strip()[:140]}")
        m = re.search(INJECTION, l, re.I)
        if m:
            ev.append(f"{f}:{i}: instruction-like phrase: {ctx(l, m)}")
    out.append(finding("I3", "FAIL" if ev else "PASS", "No hidden text or reviewer-directed instructions in the sources", ev))

    # ---- I4 placeholders
    pat = PLACEHOLDER + ("|" + "|".join(args.placeholder) if args.placeholder else "")
    ev = [f"{f}:{i}: {ctx(l, m)}" for f, i, l in doc for m in re.finditer(pat, l)
          if not re.match(r"\s*\\(re|provide)?newcommand|\s*\\def", l)]
    out.append(finding("I4", "FAIL" if ev else "PASS", "No placeholders or unfinished text in the sources", ev))

    # ---- S1 supplement compiled with the paper
    sup = [f"{f}:{i}: {l.strip()}" for f, i, l in doc if re.search(r"\\input\{[^}]*suppl", l, re.I) or "\\maketitlesupplementary" in l]
    if sup:
        out.append(finding("S1", "INFO", "Supplement is compiled with the paper: split the pages before upload "
                           f"(supplementary deadline {src['deadlines_aoe']['supplementary']} AoE)", sup[:3]))
    return out
