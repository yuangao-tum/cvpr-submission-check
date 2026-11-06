# cvpr-submission-check

A Claude Code skill and a set of small Python scripts (standard library + poppler) that check a LaTeX paper against the
**official CVPR 2027 Author Guidelines** before submission. It also checks that **every cited reference exists**:
CVPR 2027 desk-rejects papers that cite non-existent work.

The rules are taken from the official sources, read on 2026-11-06:
[Author Guidelines](https://cvpr.thecvf.com/Conferences/2027/AuthorGuidelines) ·
[Dates](https://cvpr.thecvf.com/Conferences/2027/Dates) ·
[author kit](https://media.eventhosts.cc/Conferences/CVPR2027/author-kit-CVPR2027-v1-latex.zip).
`references/cvpr2027_rules.md` lists each rule with a short quote and a check ID. `scripts/refresh_sources.py` tells
you whether the official pages changed since then. The official pages always take precedence over this repository.

## What it checks

| ID | Check | How |
|---|---|---|
| F1 | 2027 template in review mode (`cvpr.sty` = 2027 kit, `[review]`, `\confYear{2027}`, no Paper ID) | automatic |
| F2 | Main text within 8 pages; references and the LLM Usage Statement excluded | automatic (from the PDF) |
| F3 | No altered margins, line spacing or base font size; US letter | automatic + your judgment |
| F4 / F5 | "LLM Usage Statement" present after the main text and before the references; tools named | automatic + your judgment |
| A1–A4 | Anonymity: identity terms, e-mails, first-person self-citations, acknowledgments, PDF metadata, every URL | evidence for your decision |
| I1 | Every cited reference exists (arXiv ID, OpenAlex, DBLP, Crossref); first author and year agree; published versions of arXiv entries | automatic, with a list of entries to confirm by hand |
| I3 | Hidden text / prompt injection (white text, tiny fonts, instruction-like phrases) | automatic |
| I4 | Unresolved references (`??`) and placeholders | automatic |
| S1 | Supplement compiled with the paper: page split | automatic |
| M1–M8 | OpenReview profiles, reciprocal-reviewer quota, author list, dual submission, human subjects, datasets, societal impact, media embargo | checklist |

## Install as a Claude Code skill

```bash
git clone https://github.com/yuangao-tum/cvpr-submission-check ~/.claude/skills/cvpr-submission-check
```

Then ask Claude Code to "run the CVPR submission check". `SKILL.md` gives Claude the procedure.

## Use the scripts directly

Requirements: Python ≥ 3.9, `pdftotext` / `pdfinfo` / `pdffonts` (poppler-utils), internet access for the reference check.

```bash
# 1. are the rules still current?
python3 -I scripts/refresh_sources.py

# 2. build your review PDF (keep main.aux), then:
python3 -I scripts/run_checks.py \
    --main paper/main.tex --pdf build/main.pdf --aux build/main.aux \
    --identity ~/private/identity.txt \
    --placeholder '\[PENDING' \
    --out check_out/
```

Outputs: `check_out/report.md` (every rule, worst first), `check_out/refs_report.md` (one row per cited reference),
JSON versions of both, and a cache of the API answers so that a re-run is fast. Exit code 2 = some FAIL, 1 = some WARN.

`--identity` is a private file with one term per line: author names, institutions, lab and vehicle names, grant IDs,
e-mail domains, GitHub user names. **Keep it, and the reports on your paper, out of public repositories.** The
reference check sends only the cited works' titles and arXiv IDs to the public indexes.

## Limits

- The page check reads the PDF text, not its geometry: look at the last page of the main text yourself.
- The hidden-text check catches the usual LaTeX constructs and phrases, not every possible trick.
- DBLP may refuse automated clients (bot check), and OpenAlex gives clients without a key a daily budget (set
  `OPENALEX_API_KEY` to a free key to raise it). An index that refuses is skipped for the rest of the run and reported.
  Entries not found while an index was unavailable are `UNCHECKED`, not `NOT_FOUND`: re-run later (cached answers are
  reused) or confirm them by hand. arXiv title search and Crossref remain as fallbacks.
- `NON_PAPER` entries (model cards, blogs, repositories) are checked by fetching their URL (HTTP status and page title).
- `NOT_FOUND` does not prove that a reference is fabricated, and `VERIFIED` does not prove that the bib entry is
  complete. Confirm the flagged entries by hand.

## License

MIT, see [LICENSE](LICENSE). Not affiliated with CVPR, the CVF or the IEEE.
