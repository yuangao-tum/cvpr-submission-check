---
name: cvpr-submission-check
description: Check a LaTeX paper against the official CVPR 2027 Author Guidelines before submission (template, 8-page limit, LLM Usage Statement, anonymity, links, prompt injection, placeholders, supplement split) and verify that every cited reference exists (arXiv, DBLP, OpenAlex, Crossref). Use before the CVPR paper registration, paper or supplementary deadline, after any late edit, or when asked "is the paper ready to submit", "check the CVPR rules", "check our references", "desk-reject check".
---

# CVPR 2027 submission check

The rules come from the official CVPR 2027 sources, read on 2026-11-06 and summarized with short quotes and check IDs in
`references/cvpr2027_rules.md`. The page is authoritative; this skill only helps apply it.

## Procedure

1. **Are the rules current?** Run `python3 -I scripts/refresh_sources.py`. It re-fetches the Author Guidelines, the Dates
   page and the author kit and compares them with the hashes in `references/sources.json`. If anything changed, read the
   printed diff, update `references/cvpr2027_rules.md` and the checks, then run with `--update`.
2. **Build the review PDF** the way it will be uploaded (the venue's compiler and fonts, e.g. Overleaf pdfLaTeX), keeping
   `main.aux`. Use the final sources: no revision marks, all placeholders filled.
3. **Write a private identity file** (one term per line: author names, institutions, lab, grant IDs, e-mail domains,
   GitHub user names, the research vehicle's or lab's names). Never commit it or the outputs to a public repository.
4. **Run the checks:**
   ```bash
   python3 -I scripts/run_checks.py --main paper/main.tex --pdf build/main.pdf --aux build/main.aux \
       --identity ~/private/identity.txt --placeholder '\[PENDING' --out check_out/
   ```
   This writes `check_out/report.md` (all rules, worst first) and `check_out/refs_report.md` (one row per cited
   reference). Exit code 2 = some FAIL, 1 = some WARN. Add `--skip-refs` when offline.
5. **Resolve every FAIL, then every WARN.** For each WARN, decide and write the decision down: a link that neither
   expands content nor identifies the authors may stay; a negative `\vspace` count is information, not a violation.
   - `NOT_FOUND` references: open the work (DOI, arXiv, publisher page) and confirm it exists and the entry matches.
     Citations to non-existent work are a desk-rejection reason. Fix titles that were misspelled, then re-run.
   - `CHECK_METADATA`: correct the first author or year in the bib, or confirm the difference (e.g. arXiv v1 year).
   - `UNCHECKED`: an index refused during the lookup (rate limit, daily budget); re-run later or confirm by hand.
   - `NON_PAPER` (model cards, laws, websites): the report shows each URL's HTTP status and title; confirm each by hand.
   - `PUBLISHED`: an arXiv-only entry has a peer-reviewed version; prefer citing it.
6. **Go through the MANUAL rows** with the authors (OpenReview profiles and enrollment by the registration deadline,
   reciprocal-reviewer quota, author list, dual submission, human subjects, dataset release, societal impact,
   media embargo, supplement anonymity and deadline).
7. **Re-run after every late edit** and on the final PDF before upload; keep the report with the submission records.

## What the scripts decide and what they do not

| Rule | Automatic | Needs a person |
|---|---|---|
| F1 template | `cvpr.sty` hash = 2027 kit, `[review]` option, `\confYear{2027}`, no Paper ID in the header | – |
| F2 eight pages | page of the "LLM Usage Statement" heading (≤ 8, or first text of page 9) | look at the page once |
| F3 layout | geometry, margins, baseline, base font size changes; letter size | whether changes are "substantial" |
| F4/F5 LLM statement | heading present and before the references; sentences about assistants or editing that name no tool | parts affected and extent |
| A1–A4 anonymity, links | identity terms, e-mails, first-person self-citations, acknowledgments, PDF metadata, every URL | each URL's purpose |
| I1 references | existence by ID and title; first author, year; published versions | NOT_FOUND / NON_PAPER entries |
| I3 prompt injection | white/invisible text constructs; instruction-like phrases in sources and PDF text | – |
| I4 placeholders | `??`, `[?]`, TODO/TBD/FIXME/XXX, `--placeholder` patterns | – |
| S1 supplement | supplementary pages appended; page split | upload by the supplementary deadline |

Limits: the page check reads text, not geometry, so look at the last page of the main text yourself. The hidden-text
check finds the usual LaTeX constructs and phrases, not every possible trick. The reference lookup uses public APIs
(about 1-2 s per entry): it sends only the cited works' titles and IDs, and caches answers in the output folder.

## Key dates (AoE)

Paper registration Nov 10, 2026 (all co-authors with complete OpenReview profiles; no author changes afterwards) ·
paper Nov 16, 2026 · supplementary material Nov 23, 2026.
