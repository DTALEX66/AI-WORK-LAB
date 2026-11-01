#!/usr/bin/env python3
"""Gate: may this commit be pushed? Only if a full-gate receipt names it and says GATE_EXIT=0.

Why this exists: the ordering rule (commit -> verify at HEAD -> push) has been broken three times,
twice by me. ERR-181 pushed a head whose own gate run had already reported red, because the wrapper's
exit code was read instead of the receipt. This one was pushed after a governance-only run. A receipt
that does not say which head it describes cannot answer "was THIS head verified", so
`run_quality_gate.py` now stamps `GATE_HEAD=<sha>` into its own output and this tool matches it.

Verdicts, each with a distinct exit code so a caller cannot mistake one for another:
  PUSH_PERMIT_OK            0   a receipt names this head and carries GATE_EXIT=0
  PUSH_PERMIT_REFUSE        1   NO_RECEIPT / RECEIPT_RED / NO_EXIT_LINE / NOT_A_COMMIT
  PUSH_PERMIT_NOT_RUN       3   the tool itself cannot work (no runs dir, git missing)
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE_HEAD = re.compile(r"^GATE_HEAD=([0-9a-f]{40})\b", re.MULTILINE)
GATE_HEAD_END = re.compile(r"^GATE_HEAD_END=([0-9a-f]{40})\b", re.MULTILINE)
GATE_EXIT = re.compile(r"^GATE_EXIT=(-?\d+)\s*$", re.MULTILINE)
GATE_FULL = re.compile(r"GATE_FULL=(\w+)")
GATE_STAGES = re.compile(r"^GATE_STAGES ran=(\d+) planned=(\d+) full=(\w+)", re.MULTILINE)
GATE_DIRTY = re.compile(r"^GATE_DIRTY=\S+ dirty_paths=(\d+)", re.MULTILINE)
GATE_DRIFT = re.compile(r"^GATE_SOURCE_DRIFT=(\w+)", re.MULTILINE)


def qualification(body: str, head: str) -> tuple[bool, str]:
    """Why this receipt does (or does not) certify `head` for a push.

    Every field is read from the receipt because a push decision cannot rest on anything the tool did not
    record: the runner has to be the one that says which bytes it judged, how many stages it planned, and
    whether those bytes moved underneath it.
    """
    stages = GATE_STAGES.search(body)
    if not stages:
        # a receipt predating the source-binding fields says which head it started on and nothing about what
        # it finished, so it cannot support a verdict at all -- not even a narrow one
        return False, "UNBOUND_RECEIPT(no GATE_STAGES/GATE_HEAD_END fields)"
    full = GATE_FULL.search(body)
    if not full or full.group(1) != "yes":
        return False, "PARTIAL_ONLY"
    ran, planned, claimed_full = stages.groups()
    if claimed_full != "yes" or int(planned) == 0 or int(ran) != int(planned):
        return False, f"STAGES_MISSING ran={ran} planned={planned}"
    if not GATE_HEAD_END.search(body) or GATE_HEAD_END.search(body).group(1) != head:
        return False, "HEAD_MOVED_DURING_RUN"
    drift = GATE_DRIFT.search(body)
    if not drift:
        return False, "UNBOUND_RECEIPT(no GATE_SOURCE_DRIFT)"
    if drift.group(1) != "yes" and drift.group(1) != "no":
        return False, f"UNREADABLE_DRIFT({drift.group(1)})"
    if drift.group(1) == "yes":
        return False, "SOURCE_CHANGED_DURING_RUN"
    dirty = GATE_DIRTY.search(body)
    if not dirty:
        return False, "UNBOUND_RECEIPT(no GATE_DIRTY)"
    if int(dirty.group(1)) != 0:
        return False, f"DIRTY_RECEIPT dirty_paths={dirty.group(1)}"
    exits = GATE_EXIT.findall(body)
    if not exits:
        return False, "NO_EXIT_LINE"
    if exits[-1] != "0":
        return False, f"RECEIPT_RED GATE_EXIT={exits[-1]}"
    return True, "QUALIFIED"


def decide(head: str, files: list[Path], allow_partial: bool = False) -> tuple[int, str]:
    """Pure: the verdict for one head against a set of receipt files.

    A green verdict is chosen only among receipts that qualify for this head. The earlier version picked
    "any receipt naming the head whose last exit line is 0", which meant one narrow successful run could
    outvote a failed full verification of the same commit -- the exact confusion (a cheap green read as a
    verified head) that this tool exists to remove. With `--allow-partial` the caller says explicitly that a
    narrow run is what it means; the qualification still has to hold for the receipts it accepts.
    """
    matching = [(p, read(p)) for p in files]
    naming = [(p, body) for p, body in matching if f"GATE_HEAD={head}" in body]
    if not naming:
        seen = {m.group(1) for _, b in matching for m in [GATE_HEAD.search(b)] if m}
        return 1, (f"PUSH_PERMIT_REFUSE NO_RECEIPT head={head[:8]} receipts={len(files)} "
                   f"heads_with_receipts={len(seen)} — this head has never been through a full gate")

    qualified: list[tuple[Path, str]] = []
    refusals: dict[str, list[str]] = {}
    # A refusal keeps its full sentence, not just the leading token. `RECEIPT_RED GATE_EXIT=7` and
    # `STAGES_MISSING ran=7 planned=50` are the parts an operator acts on, and when several receipts name
    # the same head the summary line below is the only place they can still surface.
    details: list[tuple[str, str, bool]] = []
    partial_green: list[Path] = []
    for path, body in naming:
        ok, reason = qualification(body, head)
        if ok:
            qualified.append((path, body))
        else:
            refusals.setdefault(reason.split(" ")[0].split("(")[0], []).append(path.name)
            details.append((path.name, reason, "GATE_FULL=yes" in body))
            if not ok and "GATE_FULL=yes" not in body and GATE_EXIT.findall(body)[-1:] == ["0"]:
                partial_green.append(path)
    if qualified:
        return 0, (f"PUSH_PERMIT_OK head={head[:8]} receipt={shown(qualified[0][0])} "
                   f"qualified={len(qualified)}")
    if allow_partial and partial_green:
        return 0, (f"PUSH_PERMIT_OK head={head[:8]} receipt={shown(partial_green[0])} "
                   f"allow_partial=explicit narrow-run-verdict")
    full_red = [name for reason, names in refusals.items() if reason == "RECEIPT_RED" for name in names]
    if full_red and partial_green:
        return 1, (f"PUSH_PERMIT_REFUSE MIXED_RECEIPTS head={head[:8]} "
                   f"full_red={full_red} narrow_green={[p.name for p in partial_green]} — a narrow green "
                   f"run cannot outvote a failed full verification of this commit")
    # Rank by whether the receipt claimed a full verification, then by name for a stable message: the
    # receipt that could have certified this head is the one whose specific failure is the answer. A
    # narrow run's PARTIAL_ONLY is not a diagnosis of the truncated full run lying beside it.
    file_name, reason, _claimed = sorted(details, key=lambda item: (not item[2], item[0]))[0]
    key = reason.split(" ")[0].split("(")[0]
    names = refusals[key]
    return 1, (f"PUSH_PERMIT_REFUSE {reason} head={head[:8]} receipts={names[:3]} "
               f"count={len(names)} — {file_name} names this head but does not certify it")


def resolve(head: str, cwd: Path) -> str | None:
    """Expand a short sha to the 40-hex form receipts carry, or None if git refuses it."""
    out = subprocess.run(["git", "rev-parse", "--verify", f"{head}^{{commit}}"],
                         cwd=cwd, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    value = (out.stdout or "").strip()
    return value if out.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", value) else None


def receipts(runs: Path) -> list[Path]:
    if not runs.is_dir():
        return []
    return sorted(p for p in runs.rglob("*.log") if p.is_file())


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def shown(path: Path) -> str:
    """Repo-relative when it is inside the repo, absolute otherwise (a temp receipt in a test)."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)




def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--head", required=True, help="the commit about to be pushed (any rev-parse form)")
    ap.add_argument("--runs", default=str(ROOT / ".project-local" / "runs"))
    ap.add_argument("--allow-partial", action="store_true",
                    help="accept a receipt that ran fewer than the full gate set")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="push even while the worktree holds uncommitted changes (the commit itself is "
                         "immutable, but the verification may have read the dirty bytes)")
    args = ap.parse_args(argv)

    full = resolve(args.head, ROOT)
    if full is None:
        print(f"PUSH_PERMIT_REFUSE NOT_A_COMMIT {args.head!r} does not resolve in {ROOT}")
        return 1
    if not Path(args.runs).is_dir():
        print(f"PUSH_PERMIT_NOT_RUN no runs directory at {args.runs}")
        return 3
    if not args.allow_dirty:
        status = subprocess.run(["git", "status", "--porcelain=v1", "-uall"], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        paths = [line for line in (status.stdout or "").splitlines() if line.strip()]
        if paths:
            print(f"PUSH_PERMIT_REFUSE LIVE_DIRTY head={full[:8]} uncommitted_paths={len(paths)} "
                  f"first={paths[0][:60]!r} — the bytes you are pushing are not the bytes anyone verified; "
                  f"commit them and verify again, or pass --allow-dirty when you mean to push a subset")
            return 1
    code, message = decide(full, receipts(Path(args.runs)), allow_partial=args.allow_partial)
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
