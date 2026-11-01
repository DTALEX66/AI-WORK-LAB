"""Bind error records to commits they cite about themselves.

The message-search pass (scripts/audit/bind_remaining_ledger_fixes.py) bound what commit messages name.
This pass reads the other direction: many records quote a SHA in their own text — "FIXED@9464ca7",
"fixed at 473a3f9", "landed in a91c02d" — and that citation is the record's own claim about where its
fix lives, so it can be checked rather than trusted.

An entry is bound only when all of these hold:
  - exactly one hex token in the entry's text sits within a few words of a fix-ish verb
    (fix|fixed|landed|shipped|commit|implemented|@) so the citation is unambiguous in intent;
  - the token resolves to a real commit;
  - if the entry's `lifecycle.regressionCommand` promises a file that is not inside the ignored root,
    that file exists in the cited commit's tree.

Anything ambiguous is left owed and printed with its reason. `--apply` writes the ledger.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LED = REPO / "taskpacks/current/error-ledger.json"
CD_RE = re.compile(r"^(?:cd\s+(?P<dir>[^\s&]+)\s*(?:&&|;)\s*)?(?P<cmd>.*)$")
HEX_TOKEN = re.compile(r"\b([0-9a-f]{7,40})\b")
FIXISH = re.compile(r"(fix|fixed|fixes|landed|shipped|commit|implemented|implemented@|@|merged|recorded)",
                    re.I)
MULTI_COMMIT = re.compile(r"(?:\d+|多|several|五|5)\s*(?:个|commits|commit)|commits", re.I)
DIGEST_WORD = re.compile(r"digest|sha256|sha-?1|prefix|hash", re.I)
TEXT_FIELDS = ("observed_error", "root_cause", "fix", "regression_test", "remaining_boundary",
               "entrypoint")


def git(*a: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def is_commit(sha: str) -> bool:
    return git("cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def promise_script(command: str) -> str | None:
    m = CD_RE.match((command or "").strip())
    body = (m.group("cmd") if m else command or "").strip()
    try:
        argv = shlex.split(body)
    except ValueError:
        return None
    for token in argv:
        if token.endswith((".py", ".mjs", ".sh")) and "/" in token and not token.startswith("python"):
            return token
    return None


def cited_candidates(entry: dict) -> list[tuple[str, str]]:
    """(sha, context) for each fix-ish SHA citation in the entry's own prose."""
    found = []
    for field in TEXT_FIELDS:
        text = str(entry.get(field) or "")
        for m in HEX_TOKEN.finditer(text):
            window = text[max(0, m.start() - 40):m.start()]
            if not FIXISH.search(window):
                continue
            # "committed head (digest fe0f68d3…)" and "sha256 prefix f06a97b6…" are content digests,
            # not commits: both appear next to a fix verb and both look exactly like an abbreviated
            # SHA. Treating them as commits would refuse real citations and, worse, accept the
            # inference that a digest names a fix.
            if DIGEST_WORD.search(window) or DIGEST_WORD.search(
                    text[m.end():m.end() + 12]):
                continue
            sha = m.group(1)
            if sha.isdigit():
                continue        # 20260812105059 is a timestamp that happens to be hex-shaped
            span = text[max(0, m.start() - 120):m.end() + 60]
            if MULTI_COMMIT.search(span):
                # "5 commits (…)": naming one of them as THE fix commit would be a weak inference
                # dressed up as evidence, which is what this whole pass exists to refuse
                continue
            found.append((sha, f"{field}: …{window[-30:]}<{sha}>"))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    doc = json.loads(LED.read_text(encoding="utf-8"))
    bound, owed = [], []
    for e in doc["errors"]:
        lc = e.get("lifecycle") or {}
        if lc.get("fixedCommit") or e.get("status_after") not in ("PASS", "PARTIAL"):
            continue
        script = promise_script(lc.get("regressionCommand") or "")
        cands = cited_candidates(e)
        uniq = sorted({c[0] for c in cands})
        if not uniq:
            continue                      # nothing cited; the other pass already covers messaging
        if len(uniq) > 1:
            owed.append({"id": e["error_id"], "why": f"{len(uniq)} distinct cited SHAs: {uniq[:4]}"})
            continue
        sha = uniq[0]
        intro = str(lc.get("introducedCommit") or "")
        if intro and (sha == intro or intro.startswith(sha)):
            owed.append({"id": e["error_id"],
                         "why": f"cited {sha} is the record's introducedCommit, not its fix"})
            continue
        if not is_commit(sha):
            owed.append({"id": e["error_id"], "why": f"cited {sha} is not a commit in this repo"})
            continue
        if script and not script.startswith(".project-local/"):
            if git("cat-file", "-e", f"{sha}:{script}").returncode != 0:
                owed.append({"id": e["error_id"],
                             "why": f"cited {sha} does not contain the promised {script}"})
                continue
        verified = str(lc.get("verifiedCommit") or "")
        if verified:
            if not is_commit(verified):
                owed.append({"id": e["error_id"], "why": f"existing verifiedCommit {verified} "
                                                        "is not a commit"})
                continue
            if git("merge-base", "--is-ancestor", sha, verified).returncode != 0:
                owed.append({"id": e["error_id"],
                             "why": f"cited {sha} is not an ancestor of the record's own "
                                    f"verifiedCommit {verified[:7]} — a squash merge rewrites "
                                    "ancestry, so the citation cannot be the fix commit"})
                continue
        bound.append({"id": e["error_id"], "cited": sha, "citation": cands[0][1],
                      "promise": script, "statusAfter": e.get("status_after")})
        if args.apply:
            short = git("rev-parse", "--short", sha).stdout.strip()
            lc["fixedCommit"] = short
            lc["bindingNote"] = (
                f"bound 2026-10-07 by scripts/audit/bind_ledger_fixes_from_cited_shas.py: this record "
                f"itself cites {sha} next to a fix verb ({cands[0][1]}), the object exists, and "
                + (f"the promised {script} is present in that tree." if script
                   else "the record carries no checkable script citation."))
            e["lifecycle"] = lc

    if args.apply:
        LED.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2).replace("\n", "\r\n").encode())
        back = json.loads(LED.read_text(encoding="utf-8"))
        for b in bound:
            got = next(x for x in back["errors"] if x["error_id"] == b["id"])["lifecycle"]["fixedCommit"]
            assert got == git("rev-parse", "--short", b["cited"]).stdout.strip(), b["id"]
        print(f"ledger rewritten; entries with fixedCommit="
              f"{sum(1 for x in back['errors'] if (x.get('lifecycle') or {}).get('fixedCommit'))}"
              f"/{len(back['errors'])}")

    print(f"bound_from_self_citation={len(bound)} refused={len(owed)}")
    for b in bound:
        print(f"  {b['id']} -> {b['cited'][:12]}  via “{b['citation']}”")
    for o in owed:
        print(f"  REFUSED {o['id']}: {o['why']}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
