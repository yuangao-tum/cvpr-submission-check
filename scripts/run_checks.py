"""Run the CVPR 2027 submission checks on a LaTeX paper and its compiled PDF; write report.md / report.json.

  python3 -I scripts/run_checks.py --main paper/main.tex --pdf build/main.pdf --aux build/main.aux \
      --bib paper/main.bib --identity identity.txt --out check_out/

--identity: a private text file, one term per line (author names, institutions, grant IDs, lab names, GitHub user
names, e-mail domains). Keep it and the outputs out of public repositories.
--placeholder: extra regex for project-specific placeholders, e.g. '\\[PENDING' (repeatable).
--skip-refs: skip the online reference check (rule I1), e.g. offline.
Exit code: 2 if any FAIL, 1 if any WARN, else 0.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cvprcheck import expand_inputs, finding, load_sources, report_markdown  # noqa: E402
import check_pdf  # noqa: E402
import check_refs  # noqa: E402
import check_tex  # noqa: E402

MANUAL = [
    ("M1", "All authors: complete OpenReview profile and author enrollment (data-use and AI consent) by the registration deadline"),
    ("M2", "Reciprocal-reviewer quota: at least one author with an accepted main-track paper at a listed venue, on OpenReview; "
           "at most 25 submissions per author"),
    ("M3", "Author list final at registration (no additions or removals); order final at submission"),
    ("A5", "Own concurrent submissions: anonymized copy in the supplement, cited, difference argued"),
    ("I2", "Every reference contributes to the paper (no citation padding)"),
    ("I6", "No overlapping submission elsewhere during review (20% overlap rule)"),
    ("M4", "Human or animal subjects: IRB (official name) or why none; consent"),
    ("M5", "A dataset claimed as a contribution is available by camera-ready; no withdrawn datasets"),
    ("M6", "Significant potential negative impacts discussed"),
    ("M7", "No media or public mention of the paper as a CVPR submission"),
    ("S2", "Supplement anonymous, no content-expanding links; uploaded by the supplementary deadline"),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--main", required=True, help="main .tex file of the paper")
    ap.add_argument("--pdf", help="compiled PDF (review version, as it will be uploaded or with the supplement appended)")
    ap.add_argument("--aux", action="append", default=[], help="main.aux of that build (cited keys); repeatable")
    ap.add_argument("--bib", action="append", default=[], help=".bib file(s); default: *.bib next to the main file")
    ap.add_argument("--identity", help="private file with identifying terms, one per line")
    ap.add_argument("--placeholder", action="append", default=[], help="extra placeholder regex (repeatable)")
    ap.add_argument("--skip-refs", action="store_true")
    ap.add_argument("--out", default="cvpr_check_out")
    args = ap.parse_args()
    if not args.bib:
        args.bib = [str(p) for p in sorted(Path(args.main).resolve().parent.glob("*.bib"))]
    args.identity_terms = []
    if args.identity:
        args.identity_terms = [l.strip() for l in Path(args.identity).read_text().splitlines()
                               if l.strip() and not l.lstrip().startswith("#")]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    src = load_sources()

    findings = check_tex.run(args)
    pdf_meta = {}
    if args.pdf:
        f, pdf_meta = check_pdf.run(args)
        findings += f
    else:
        findings.append(finding("F2", "MANUAL", "Page limit not checked (no --pdf given)"))
    if args.skip_refs:
        findings.append(finding("I1", "MANUAL", "Reference existence not checked (--skip-refs)"))
    else:
        rows, _ = expand_inputs(Path(args.main).resolve())
        findings += check_refs.run(args, rows, out_dir)
    for rid, title in MANUAL:
        findings.append(finding(rid, "MANUAL", title))

    d = src["deadlines_aoe"]
    meta = [f"Checked {dt.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}: `{args.main}`"
            + (f", `{args.pdf}` ({pdf_meta.get('pages')} pages)" if args.pdf else ""),
            f"Rules: references/cvpr2027_rules.md (sources retrieved {src['guidelines']['retrieved']}; "
            "run scripts/refresh_sources.py to see whether they changed).",
            f"Deadlines (AoE): registration {d['paper_registration']}, paper {d['paper_submission']}, "
            f"supplement {d['supplementary']}."]
    md = report_markdown(findings, "CVPR 2027 submission check", meta)
    (out_dir / "report.md").write_text(md)
    (out_dir / "report.json").write_text(json.dumps({"meta": meta, "pdf": pdf_meta, "findings": findings}, indent=1))
    print(md)
    st = {f["status"] for f in findings}
    sys.exit(2 if "FAIL" in st else 1 if "WARN" in st else 0)


if __name__ == "__main__":
    main()
