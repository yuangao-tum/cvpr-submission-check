"""Re-fetch the CVPR 2027 Author Guidelines, the Dates page and the author kit; report whether they changed
since references/sources.json was written.

  python3 -I scripts/refresh_sources.py            # compare only
  python3 -I scripts/refresh_sources.py --update   # also rewrite the hashes in references/sources.json

The full page text is cached outside the repository (~/.cache/cvpr-submission-check/<date>/) so that a later run can
print a line diff. The repository stores only hashes and short quotes (references/cvpr2027_rules.md).
If a hash changed, re-read the changed lines and update references/cvpr2027_rules.md before trusting the checks.
"""
import argparse
import datetime as dt
import difflib
import html
import io
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cvprcheck import ROOT, USER_AGENT, sha256_text  # noqa: E402

import hashlib  # noqa: E402
import urllib.request  # noqa: E402

CACHE = Path.home() / ".cache" / "cvpr-submission-check"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def page_text(raw):
    """Visible text of a conference page, one block per line (scripts, styles, navigation removed)."""
    t = raw.decode("utf-8", errors="replace")
    t = re.sub(r"(?is)<(script|style|nav|header|footer).*?</\1>", "", t)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>|</div>|</tr>", "\n", t)
    t = re.sub(r"(?i)<li[^>]*>", "\n- ", t)
    t = re.sub(r"(?s)<[^>]+>", "", t)
    lines = [re.sub(r"\s+", " ", l).strip() for l in html.unescape(t).split("\n")]
    keep = [l for l in lines if l and l != "-"]
    # Drop volatile lines (CSRF tokens, "Successful Page Load", time-zone widgets).
    keep = [l for l in keep if not re.search(r"Successful Page Load|Your time zone is|CSP Test", l)]
    return "\n".join(keep) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="write the new hashes into references/sources.json")
    args = ap.parse_args()
    src_path = ROOT / "references" / "sources.json"
    src = json.loads(src_path.read_text())
    today = dt.date.today().isoformat()
    out_dir = CACHE / today
    out_dir.mkdir(parents=True, exist_ok=True)
    changed = False
    for name in ("guidelines", "dates"):
        s = src[name]
        text = page_text(fetch(s["url"]))
        (out_dir / f"{name}.txt").write_text(text)
        h = sha256_text(text)
        same = h == s["sha256_text"]
        print(f"{name}: {'unchanged' if same else 'CHANGED'} ({s['url']})")
        if not same:
            changed = True
            prev = sorted(p for p in CACHE.glob(f"*/{name}.txt") if p.parent.name < today)
            if prev:
                diff = difflib.unified_diff(prev[-1].read_text().splitlines(), text.splitlines(),
                                            f"{prev[-1].parent.name}", today, lineterm="", n=0)
                print("\n".join(list(diff)[:200]))
            else:
                print(f"  no earlier cached copy to diff against; read {out_dir / (name + '.txt')}")
            if args.update:
                s["sha256_text"] = h
                s["retrieved"] = today
    kit = src["author_kit"]
    raw = fetch(kit["url"])
    (out_dir / "author-kit.zip").write_bytes(raw)
    zh = hashlib.sha256(raw).hexdigest()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        files = {Path(n).name: z.read(n) for n in z.namelist() if not n.endswith("/")}
    sty = hashlib.sha256(files.get("cvpr.sty", b"")).hexdigest()
    print(f"author kit zip: {'unchanged' if zh == kit['sha256_zip'] else 'CHANGED'}; "
          f"cvpr.sty: {'unchanged' if sty == kit['sha256_cvpr_sty'] else 'CHANGED'}")
    if zh != kit["sha256_zip"] or sty != kit["sha256_cvpr_sty"]:
        changed = True
        if args.update:
            kit.update(sha256_zip=zh, sha256_cvpr_sty=sty, retrieved=today,
                       sha256_bst=hashlib.sha256(files.get("ieeenat_fullname.bst", b"")).hexdigest())
    if args.update and changed:
        src_path.write_text(json.dumps(src, indent=2) + "\n")
        print("sources.json updated; now review references/cvpr2027_rules.md against the diff above.")
    print(f"cached copies: {out_dir}")
    sys.exit(1 if changed and not args.update else 0)


if __name__ == "__main__":
    main()
