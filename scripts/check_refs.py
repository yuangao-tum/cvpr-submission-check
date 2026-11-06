"""I1: does every cited reference exist? Looks each cited BibTeX entry up by arXiv ID (arXiv API) and by title
(OpenAlex and DBLP, then Crossref), and compares title, first author and year.

Statuses per entry:
  VERIFIED         title found; first author and year agree (year within 1)
  CHECK_METADATA   title found, but the first author or year differs: fix the entry or confirm by hand
  NOT_FOUND        no source has this title: confirm by hand that the work exists (fabricated citations are a
                   desk-rejection reason)
  NON_PAPER        @misc/@manual/@online/@software entry not found in paper indexes (model cards, laws, websites):
                   confirm by hand
Extra flag: PUBLISHED   the entry cites arXiv but OpenAlex or DBLP lists a peer-reviewed version (consider citing it).

Only metadata of the cited works (titles, IDs) is sent to the public APIs; nothing from the paper itself.
"""
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

from cvprcheck import Http, bib_authors, delatex, finding, norm_text, parse_bib, surname, title_similarity

INTERVALS = {"export.arxiv.org": 3.1, "dblp.org": 1.5, "api.openalex.org": 0.3, "api.crossref.org": 0.6}
NON_PAPER_TYPES = {"misc", "manual", "online", "software", "electronic", "webpage", "dataset", "unpublished"}
MATCH = 0.90


def cited_keys(aux_files, tex_rows):
    keys = []
    for aux in aux_files:
        t = Path(aux).read_text(errors="replace")
        for m in re.finditer(r"\\citation\{([^}]*)\}|\\abx@aux@cite\{[^}]*\}\{([^}]*)\}", t):
            for k in (m.group(1) or m.group(2)).split(","):
                k = k.strip()
                if k and k != "*" and k not in keys:
                    keys.append(k)
    where = {}
    for f, i, l in tex_rows:
        for m in re.finditer(r"\\(?:no)?cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}", l):
            for k in m.group(1).split(","):
                where.setdefault(k.strip(), []).append(f"{f}:{i}")
    if not keys:  # no .aux given: fall back to the sources
        keys = list(where)
    return keys, where


def arxiv_id(e):
    blob = " ".join(e.get(f, "") for f in ("eprint", "arxiv", "journal", "note", "howpublished", "url", "volume", "booktitle"))
    m = re.search(r"(?<![\d.])(\d{4}\.\d{4,5})(v\d+)?(?![\d])", blob) or re.search(r"\b([a-z\-]+(?:\.[A-Z]{2})?/\d{7})\b", blob)
    return m.group(1) if m else None


def is_arxiv_only(e):
    venue = (e.get("journal", "") + " " + e.get("booktitle", "")).lower()
    return arxiv_id(e) is not None and (not venue.strip() or "arxiv" in venue or "corr" in venue)


UNAVAILABLE = set()  # indexes that refused automated access during this run (e.g. a bot check)


def _json(http, url, host):
    """GET JSON; an HTML answer (bot check) marks the host unavailable for the rest of the run and is not cached."""
    if host in UNAVAILABLE:
        return None
    body = http.get(url)
    if not body:
        return None
    if body.lstrip().startswith("<"):
        UNAVAILABLE.add(host)
        http.cache.pop(url, None)
        http._save()
        print(f"  {host} answered with HTML (bot check?); skipping it for this run", flush=True)
        return None
    return json.loads(body)


def q_arxiv(http, aid):
    body = http.get("https://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(aid))
    if not body:
        return None
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(body)
    for ent in root.findall("a:entry", ns):
        title = " ".join((ent.findtext("a:title", "", ns) or "").split())
        if not title or title.lower() == "error":
            continue
        authors = [a.findtext("a:name", "", ns) for a in ent.findall("a:author", ns)]
        year = (ent.findtext("a:published", "", ns) or "")[:4]
        return {"source": f"arXiv {aid}", "title": title, "authors": authors, "year": year, "venue": "arXiv"}
    return None


def q_dblp(http, title):
    data = _json(http, "https://dblp.org/search/publ/api?format=json&h=8&q=" + urllib.parse.quote(norm_text(title)[:200]), "dblp.org")
    if not data:
        return []
    hits = (data.get("result", {}).get("hits", {}) or {}).get("hit", []) or []
    res = []
    for h in hits:
        info = h.get("info", {})
        au = (info.get("authors") or {}).get("author", [])
        au = au if isinstance(au, list) else [au]
        venue = info.get("venue", "")
        venue = ", ".join(venue) if isinstance(venue, list) else venue
        res.append({"source": "DBLP " + info.get("key", ""), "title": info.get("title", ""), "year": str(info.get("year", "")),
                    "authors": [re.sub(r"\s+\d{4}$", "", a.get("text", "")) for a in au], "venue": venue,
                    "peer_reviewed": venue not in ("CoRR", "") and info.get("type") != "Informal and Other Publications"})
    return res


def q_openalex(http, title):
    data = _json(http, "https://api.openalex.org/works?per-page=5&search=" + urllib.parse.quote(norm_text(title)[:200]), "api.openalex.org")
    if not data:
        return []
    res = []
    for w in data.get("results", []):
        src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
        reviewed = [((l.get("source") or {}).get("display_name") or "") for l in w.get("locations", []) or []
                    if (l.get("source") or {}).get("type") in ("journal", "conference")
                    and not re.search(r"arxiv|corr|biorxiv|ssrn|research square", ((l.get("source") or {}).get("display_name") or ""), re.I)]
        res.append({"source": "OpenAlex " + (w.get("id") or "").rsplit("/", 1)[-1], "title": w.get("display_name") or "",
                    "year": str(w.get("publication_year") or ""), "venue": src, "peer_reviewed_venues": reviewed,
                    "authors": [(a.get("author") or {}).get("display_name", "") for a in w.get("authorships", [])]})
    return res


def q_crossref(http, title):
    data = _json(http, "https://api.crossref.org/works?rows=5&select=title,author,issued,container-title,DOI&query.bibliographic="
                 + urllib.parse.quote(norm_text(title)[:200]), "api.crossref.org")
    if not data:
        return []
    res = []
    for it in data.get("message", {}).get("items", []):
        res.append({"source": "Crossref " + it.get("DOI", ""), "title": (it.get("title") or [""])[0],
                    "year": str(((it.get("issued") or {}).get("date-parts") or [[""]])[0][0] or ""),
                    "venue": (it.get("container-title") or [""])[0],
                    "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in it.get("author", [])]})
    return res


def best(cands, title):
    scored = sorted(((title_similarity(title, c["title"]), c) for c in cands), key=lambda x: -x[0])
    return scored[0] if scored else (0.0, None)


def author_ok(e, cand):
    names = bib_authors(e.get("author", "") or e.get("editor", ""))
    if not names:
        return True
    s = surname(names[0])
    pool = [norm_text(a) for a in cand.get("authors", [])[:5]]
    return bool(s) and any(s in p.split() or s == p or (len(s) > 6 and s in p) for p in pool)


def year_ok(e, cand):
    y = re.search(r"\d{4}", e.get("year", "") or e.get("date", ""))
    c = re.search(r"\d{4}", cand.get("year", ""))
    return not y or not c or abs(int(y.group(0)) - int(c.group(0))) <= 1


def check_entry(http, key, e):
    title = delatex(e.get("title", ""))
    r = {"key": key, "type": e["_type"], "title": title, "year": e.get("year", ""),
         "first_author": (bib_authors(e.get("author", "")) or [""])[0], "arxiv": arxiv_id(e), "found": None,
         "similarity": 0.0, "published": None, "notes": []}
    cands = []
    if r["arxiv"]:
        a = q_arxiv(http, r["arxiv"])
        if a:
            sim = title_similarity(title, a["title"])
            if sim >= MATCH:
                cands.append((sim, a))
            else:
                r["notes"].append(f"arXiv {r['arxiv']} is \"{a['title'][:90]}\" (title differs: wrong ID?)")
        else:
            r["notes"].append(f"arXiv ID {r['arxiv']} not found")
    if title:
        sim, o = best(q_openalex(http, title), title)
        if o and sim >= MATCH:
            cands.append((sim, o))
            if is_arxiv_only(e) and o.get("peer_reviewed_venues"):
                r["published"] = f"{o['peer_reviewed_venues'][0]} ({o['source']})"
        dblp = q_dblp(http, title)
        sim, d = best(dblp, title)
        if d and sim >= MATCH:
            cands.append((sim, d))
            pub = [c for c in dblp if c.get("peer_reviewed") and title_similarity(title, c["title"]) >= MATCH]
            if is_arxiv_only(e) and pub and not r["published"]:
                r["published"] = f"{pub[0]['venue']} {pub[0]['year']} ({pub[0]['source']})"
        if not cands:
            sim, c = best(q_crossref(http, title), title)
            if c and sim >= MATCH:
                cands.append((sim, c))
    if not cands:
        r["status"] = "NON_PAPER" if e["_type"] in NON_PAPER_TYPES else "NOT_FOUND"
        return r
    sim, c = max(cands, key=lambda x: x[0])
    r.update(found=c["source"], found_title=c["title"], found_year=c.get("year", ""), found_venue=c.get("venue", ""),
             found_first_author=(c.get("authors") or [""])[0], similarity=round(sim, 3))
    a_ok = any(author_ok(e, cc) for _, cc in cands)
    y_ok = any(year_ok(e, cc) for _, cc in cands)
    if not a_ok:
        r["notes"].append(f"first author differs: bib \"{delatex(r['first_author'])}\" vs \"{r['found_first_author']}\"")
    if not y_ok:
        r["notes"].append(f"year differs: bib {r['year']} vs {r['found_year']}")
    r["status"] = "VERIFIED" if a_ok and y_ok else "CHECK_METADATA"
    return r


def run(args, tex_rows, out_dir):
    entries = {}
    for b in args.bib:
        entries.update(parse_bib(Path(b).read_text(errors="replace")))
    keys, where = cited_keys(args.aux, tex_rows)
    http = Http(Path(out_dir) / "refs_cache.json", INTERVALS)
    results, missing = [], [k for k in keys if k not in entries]
    for n, k in enumerate(keys, 1):
        if k not in entries:
            continue
        r = check_entry(http, k, entries[k])
        r["cited_at"] = where.get(k, [])
        results.append(r)
        print(f"[{n}/{len(keys)}] {r['status']:<14} {k}", flush=True)
    (Path(out_dir) / "refs_report.json").write_text(json.dumps(results, indent=1))
    write_md(results, missing, Path(out_dir) / "refs_report.md")
    count = lambda s: [r for r in results if r["status"] == s]  # noqa: E731
    out = []
    nf, np_, cm = count("NOT_FOUND"), count("NON_PAPER"), count("CHECK_METADATA")
    if UNAVAILABLE:
        out.append(finding("I1", "INFO", "Indexes that refused automated access in this run", sorted(UNAVAILABLE)))
    out.append(finding("I1", "FAIL" if nf or missing else ("WARN" if cm or np_ else "PASS"),
                       f"Every cited reference exists ({len(count('VERIFIED'))}/{len(results)} verified automatically; see refs_report.md)",
                       [f"cited key without bib entry: {k}" for k in missing]
                       + [f"NOT_FOUND {r['key']}: \"{r['title'][:100]}\" ({r['year']})" for r in nf]
                       + [f"CHECK_METADATA {r['key']}: {'; '.join(r['notes'])}" for r in cm]
                       + [f"NON_PAPER {r['key']}: \"{r['title'][:100]}\" (confirm by hand)" for r in np_]))
    pub = [r for r in results if r.get("published")]
    if pub:
        out.append(finding("I1", "INFO", f"{len(pub)} arXiv-only entries have a peer-reviewed version in DBLP",
                           [f"{r['key']}: {r['published']}" for r in pub]))
    recent = [r for r in results if re.search(r"2026", r.get("year", ""))]
    out.append(finding("I5", "MANUAL", "Contemporaneous work (public on or after 15 Sep 2026) cited and discussed",
                       [f"{len(recent)} cited entries are dated 2026; check which appeared after 15 Sep 2026 and whether any "
                        "relevant contemporaneous work is missing"]))
    return out


def write_md(results, missing, path):
    order = {"NOT_FOUND": 0, "CHECK_METADATA": 1, "NON_PAPER": 2, "VERIFIED": 3}
    lines = ["# Reference existence check (rule I1)", "",
             "Statuses: VERIFIED (title, first author, year agree), CHECK_METADATA (title found, author/year differ), "
             "NOT_FOUND (confirm by hand), NON_PAPER (model card, law, website: confirm by hand). "
             "PUBLISHED: an arXiv-only entry with a peer-reviewed version in DBLP.", ""]
    if missing:
        lines += ["Cited keys without a bib entry: " + ", ".join(missing), ""]
    lines += ["| Status | Key | Title (bib) | Found as | Notes | Cited at |", "|---|---|---|---|---|---|"]
    for r in sorted(results, key=lambda r: (order[r["status"]], r["key"])):
        found = f"{r.get('found') or ''} ({r.get('found_venue') or ''} {r.get('found_year') or ''})" if r.get("found") else ""
        notes = "; ".join(r["notes"] + ([f"PUBLISHED: {r['published']}"] if r.get("published") else []))
        cited = ", ".join(sorted(set(c.split(":")[0] for c in r.get("cited_at", []))))
        lines.append(f"| {r['status']} | {r['key']} | {r['title'][:80].replace('|', '/')} | {found.replace('|', '/')} | "
                     f"{notes.replace('|', '/')} | {cited} |")
    path.write_text("\n".join(lines) + "\n")
