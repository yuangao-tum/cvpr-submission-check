# CVPR 2027 submission rules, with check IDs

Sources, read 2026-11-06 (hashes in `sources.json`; `scripts/refresh_sources.py` reports changes):
- Author Guidelines: https://cvpr.thecvf.com/Conferences/2027/AuthorGuidelines (quotes below; § = its section)
- Dates: https://cvpr.thecvf.com/Conferences/2027/Dates
- Author kit: https://media.eventhosts.cc/Conferences/CVPR2027/author-kit-CVPR2027-v1-latex.zip

Quotes are short excerpts; the official page is authoritative. **Check** says how this skill tests the rule:
`auto` = a script decides, `assist` = a script collects evidence and a person decides, `manual` = a person checks.
**DR** marks a desk-rejection reason (§2 Desk Rejection Policy).

## Deadlines (Dates page; all Anywhere on Earth, AoE = UTC-12)

| What | Date (AoE) |
|---|---|
| Paper registration (abstract, title, all co-authors with complete OpenReview profiles and enrollment) | Nov 10, 2026 |
| Paper submission (author order final) | Nov 16, 2026 |
| Supplementary material | Nov 23, 2026 |
| Reviews released | Jan 25, 2027 |
| Final decisions | Feb 25, 2027 |

## F: format

| ID | Rule (quote) | Check |
|---|---|---|
| F1 DR | "Papers that are not properly anonymized, do not use the template, ... will be rejected without review." Desk rejection B lists "it uses the wrong template". The 2027 kit's `cvpr.sty` says `\ProvidesPackage{cvpr}[2027 LaTeX class for IEEE CVPR]` and no longer prints a Paper ID ("removed the Paper ID to reduce the risk of leaking IDs", kit README). | auto: `cvpr.sty` hash and year match the 2027 kit; `\usepackage[review]{cvpr}` active; `\confYear{2027}`; no "Paper ID" in the PDF |
| F2 DR | "Papers are limited to eight pages, including figures and tables, in the CVPR style. Additional pages containing only cited references and the mandatory LLM Usage Statement are allowed." | auto: the main text ends on page 8 or earlier (the LLM Usage Statement heading is on page ≤ 8, or is the first text of page 9) |
| F3 DR | Desk rejection B: "has substantially altered margins or fonts". | assist: lists geometry/margin/baseline/font-size changes and negative `\vspace` counts in the sources; page size letter |
| F4 DR | "Every submission must include a section titled 'LLM Usage Statement' after the main text and before the references. It does not count toward the page limit and must not reveal the authors' identity." | auto: heading present, after the main text, before the bibliography |
| F5 | The statement must "disclose any use of LLMs or other generative AI tools in the research or the writing, including for editing and grammar; name the tool(s) used, identify the parts of the paper or the research affected (for example text, figures, code, experiments, related work or ideation), and briefly describe the nature and extent of the use", or say "No LLMs or generative AI tools were used in this work". "A statement that leaves out significant information may lead to desk rejection or to referral to the ethics committee." | assist: flags sentences about assistants, editing or code that name no tool |
| F6 | Kit: "There will be no extra page charges"; references "in 9-point Times"; review copies carry the ruler and page numbers. | auto: hyperlinks and fonts reported (all fonts embedded) |

## A: anonymity (§2 Double-blind review)

| ID | Rule (quote) | Check |
|---|---|---|
| A1 DR | "the area chairs and reviewers must not be able to infer, beyond reasonable doubt, the names of the authors from the submission and the additional material. Do not include information that may identify the authors in the acknowledgments (e.g., co-workers and grant IDs) ..." Kit: "If you are Smith and Jones, do not say 'as we show in [7]', say 'as Smith and Jones show in [7]'". | assist: author names, institutions, grant IDs and e-mails (from `--identity`) in the text before the references; first-person self-citations; an acknowledgments section in the review version |
| A2 DR | Same rule, applied to the file itself. | auto: PDF metadata (Author, Title, Subject, Keywords, Creator) holds no name from `--identity`; Author field empty |
| A3 DR | "Authors may not include external links (e.g., to webpages, images, or videos) in submissions, supplementary material, or rebuttals when the links expand content or subvert the reviewing process." FAQ: "When in doubt, leave links out of the submission (even in the reference list)." | assist: every URL in the text and the bib is listed for a decision |
| A4 | FAQ: "To preserve anonymity, you cannot cite your public codebase. You can say that the code will be made publicly available." | assist: github/gitlab/huggingface URLs listed under A3 |
| A5 | Concurrent own submissions: "(1) include anonymized versions of those papers in the supplementary material; (2) cite these anonymized papers; and (3) argue in the body of your paper why your CVPR submission is non-trivially different". | manual |

## I: research integrity (§2, §4, §6)

| ID | Rule (quote) | Check |
|---|---|---|
| I1 DR | Desk rejection C: "Fabricated content, including citations to non-existent work and obvious factual fabrications." "Papers that cite non-existent work, or that contain obvious factual fabrications, will be rejected, and may be rejected without review." | auto + assist: every cited bib entry is looked up (arXiv, DBLP, OpenAlex, Crossref) by ID and title; first author and year compared; not-found entries must be checked by hand |
| I2 | "Citing irrelevant sources to inflate citation counts (your own or anyone else's) is an ethical breach. Cite only work that genuinely contributes to the paper." | manual (the reference report lists where each key is cited) |
| I3 DR | "Hiding instructions in a paper or supplementary material (for example, white-on-white text ...) to manipulate reviewers or automated tools counts as a collusion attempt and an ethics violation. Such papers will be desk-rejected". | auto: white or invisible text commands and reviewer-directed instruction phrases in the sources and the PDF text |
| I4 | Unfinished text is a "factual inaccuracy" risk and can make a paper one that "cannot be meaningfully reviewed" (desk rejection E). | auto: `??`, `[?]`, `\todo`, TODO/TBD/FIXME/XXX and user-supplied placeholder patterns in the PDF text and sources |
| I5 | Contemporaneous work: "work that first becomes publicly available on or after September 15, 2026 is generally considered contemporaneous"; authors "are expected to cite and discuss it and to provide empirical comparisons where reasonably feasible". "Any work that influenced the submission counts as prior work". | manual (the reference report lists entries dated 2026) |
| I6 DR | Dual submission: no "publication substantially similar in content (defined as 20 percent or more overlap)" submitted elsewhere during the review period; "arXiv preprints and university technical reports are not publications". | manual |

## M: administration and ethics (manual)

| ID | Rule (quote) |
|---|---|
| M1 DR | "All authors of a paper must have a valid OpenReview profile by the abstract submission deadline (Nov 10, 2026) to avoid desk rejection." Enrollment includes the data-use and AI consent. |
| M2 DR | Reciprocal-reviewer quota: "Each author may be a co-author on at most one paper in which none of the authors is an eligible reciprocal reviewer" (an accepted main-track paper at CVPR, ICCV, ECCV, WACV, ACM MM, TPAMI, IJCV, NeurIPS, ICML, ICLR, AAAI, IJCAI, JMLR, ICRA, IROS, RSS, CoRL, IJRR, T-RO, SIGGRAPH (Asia), TOG, TVCG), checked only from the OpenReview profile. At most 25 submissions per author. |
| M3 | "authors cannot be added or removed after the abstract submission deadline (Nov 10, 2026); they can only be reordered. The author order is final after the paper submission deadline (Nov 16, 2026)." |
| M4 | Human subjects: "papers reporting research on human or animal subjects must state that the research was approved or overseen by an Institutional Review Board (IRB) or equivalent body, giving that body's official name, or explain why no review was carried out", and whether consent was obtained. |
| M5 | Datasets: "If you claim a dataset as one of your contributions, it is expected to be ready and available when you submit the camera-ready paper." "papers should not use datasets that have been withdrawn by their creators". |
| M6 | "Whenever a work has significant potential negative impacts (or could be seen that way by reviewers), the submission should discuss them." |
| M7 | Media: "Papers submitted to CVPR must not be discussed with the media mentioning CVPR until they have been officially accepted"; a public note that a paper "will be submitted to CVPR" is "strongly discouraged". arXiv posting is allowed. |
| M8 | Camera-ready: "the camera-ready version must disclose any AI-generated content (text, figures, images or code) in the Acknowledgments, stating the AI system, affected sections and level of use." |

## S: supplementary material

| ID | Rule (quote) | Check |
|---|---|---|
| S1 | Optional; "may include videos, proofs, additional figures or tables, more detailed analysis of the experiments in the paper"; code upload encouraged. FAQ: no formatting requirements, "A single-column layout is permitted." Deadline Nov 23, 2026 AoE. Kit (`sec/X_suppl.tex`): compile the supplement with the paper for cross-references, then split the pages ("do not forget to delete the supplementary pages from your submission"). | auto: reports whether supplementary pages are appended to the paper PDF |
| S2 DR | Anonymity and the link rule apply to the supplement too: "Do not include information that may identify the authors ... in the supplementary material (e.g., author or institution names in demo videos, or non-anonymized attached papers)." | assist: A1/A3 scans cover the appended supplement |

Note: when the supplement is compiled with the paper, references cited only in the supplement are printed in the paper's reference list. That is the kit's intended workflow. Add new citations to the supplement before the paper deadline, or give a later-revised supplement its own bibliography.

## R: rebuttal (§3)

"The rebuttal is limited to a one-page PDF using the rebuttal template in the CVPR 2027 Submission Template." It "must maintain anonymity. It cannot include links to external material such as code or videos." "Authors should not include new contributions or experimental results in the rebuttal, especially when the reviewers have not specifically asked for them."
