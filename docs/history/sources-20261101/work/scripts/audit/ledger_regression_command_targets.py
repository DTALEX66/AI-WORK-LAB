"""Make the error ledger's promised regression proof re-runnable, or say plainly why it is not.

Every record in `taskpacks/current/error-ledger.json` promises a `regression_test` command. The
repository then moved twice — the 2026-09 convergence (`10-workflow/workflow-assistance` ->
`packages/client-neutral-core`, `services/`, `apps/observer`) and the `.hermes/task-runtime` ->
`.project-local` root move — so a record saying "this command is the proof" can name bytes that no
longer exist under that name. That is how a PASS record stops being verifiable while still reading
like one, and it is why 99 of them sat unbound.

Measured here: some operands resolve, some are the same basename at exactly one other tracked path,
some name nothing tracked at all, and some deliberately read a managed client's home (`Hermes
config.yaml`, `$CODEX_HOME/AGENTS.md`) which no checkout can contain. The tool does two things:

  * re-points the unambiguous moves, with anchored substitution so a path is replaced only when the
    whole token matches — the prefix-doubling class ERR-135 records;
  * stamps every record with `regressionTestVerifiability`, one of six labelled states, so a reader and
    a gate can tell "this proof re-runs here" from "this proof cannot re-run, and here is why".

Labels are stamped from the bytes that were actually written, never from the substitution that was
intended: a re-point that matched nothing must not be reported as one that happened. `status_after` is
never rewritten — an unverifiable promise is labelled, not silently downgraded and not silently
trusted. Everything read is tracked state (`git ls-files` plus the ledger), so the verdict cannot move
with local disk state, which is the lesson of ERR-142.

Usage:
    python scripts/audit/ledger_regression_command_targets.py            # measure only
    python scripts/audit/ledger_regression_command_targets.py --apply    # rewrite ledger + audit
Exit: 0 when every record carries a label and no ambiguity is left unadjudicated; 1 otherwise; 2 when
      the ledger cannot be parsed.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
LEDGER = REPO / "taskpacks/current/error-ledger.json"
AUDIT = REPO / "docs/audits/LEDGER_REGRESSION_COMMAND_TARGETS_2026-10-07.json"

STATES = ("RESOLVES", "REPOINTED_20261007", "PATH_GONE", "NO_FILE_OPERAND_IN_COMMAND",
          "OUT_OF_REPO_TARGET", "ADJUDICATED_BY_HAND")
EXTENSIONS = (".py", ".sh", ".ps1", ".cmd", ".cjs", ".js", ".mjs", ".ts", ".tsx", ".json",
              ".yaml", ".yml", ".md", ".rs", ".toml", ".html", ".css")
NON_FILE_WORDS = {"python", "node", "git", "cargo", "npm", "npx", "pytest", "unittest", "discover",
                  "run", "status", "diff", "check", "short", "module", "m", "c", "rg", "grep", "and",
                  "then", "test", "tests", "src", "scripts", "workflow", "task", "tasks", "source",
                  "quality", "every", "for", "the", "bytes", "url", "returned", "equal", "recorded",
                  "both", "was", "were", "must", "that", "this", "plus", "own", "step", "gate", "which"}
# an operand that addresses a managed client's home, or a bare Windows path, is outside every checkout
# by design: it is not a broken pointer, it is a claim about the live machine
OUT_OF_REPO = re.compile(r"^([A-Za-z]:[\\/]|~[\\/]|CODEX_HOME[\\/]|HERMES_HOME[\\/])")

ADJUDICATED: dict[str, dict] = {
    "ERR-045": {"state": "OUT_OF_REPO_TARGET",
                "reason": "the command greps `reasoning_effort` in the live Hermes Home config.yaml; no "
                          "checkout contains that file, so the promise is about the managed client's "
                          "state on the authoring machine. The tracked field-ownership record "
                          "(config/config-ownership.json) is what a reader can verify here."},
    "ERR-047": {"state": "OUT_OF_REPO_TARGET",
                "reason": "the command counts a line in another machine's Codex Home config.toml "
                          "(C:/Users/admin/...), which neither this checkout nor CI can contain; the "
                          "2026-09-30 audit copy under reports/audit-archive is a snapshot, not the "
                          "subject of the promise."},
    "ERR-095": {"state": "OUT_OF_REPO_TARGET",
                "reason": "the operand is `$CODEX_HOME/AGENTS.md` — a managed client projection target, "
                          "deliberately outside the repository. The overlay-block requirement is "
                          "enforced here by the skill-provenance and config-ownership gates, not by "
                          "reading that home in CI."},
    "ERR-094": {"state": "NO_FILE_OPERAND_IN_COMMAND",
                "reason": "regression_test is a prose sentence naming `MANIFEST.json` as a kind, not a "
                          "path; three archived manifests carry that basename, so choosing one would "
                          "invent a pointer the record never made."},
    "ERR-103": {"state": "REPOINTED_20261007",
                "map": {"capabilities/default.json":
                        "apps/observer/src-tauri/capabilities/default.json"},
                "reason": "two tracked files carry the basename capabilities/default.json (observer and "
                          "token-monitor), so the matcher cannot choose. The record decides: its "
                          "regression test is apps/observer/tests/test_desktop_component_contract.js "
                          "and its symptom is the observer's caption cluster and zoom controls, so the "
                          "operand is the OBSERVER's Tauri capability file. Applied to this record only, "
                          "never as a global substitution."},
}


def tracked_paths() -> list[str]:
    raw = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "-z"],
                         cwd=REPO, capture_output=True).stdout
    return [p.decode("utf-8", "replace") for p in raw.split(b"\0") if p]


def operands(command: str) -> list[str]:
    """File-shaped tokens in a command. Quotes, markdown and sentence punctuation are not paths.

    A pytest node id (`tests/x.py::Class::test_y`) is one promise about one file, so the node part is
    dropped before shaping is judged; leaving it attached made three of the newest records read as
    PATH_GONE over a file that is tracked and green.
    """
    out: list[str] = []
    for chunk in re.split(r"&&|\|\||;", str(command)):
        for token in chunk.split():
            tok = token.strip("\"'`()<>{}[],")
            if "::" in tok:
                tok = tok.split("::", 1)[0]
            if len(tok) > 2 and tok.endswith(".") and not re.search(r"\.[A-Za-z]{1,8}$", tok):
                tok = tok[:-1]                      # a sentence period, never part of a path
            if not tok or "=" in tok or tok.startswith("-"):
                continue
            if "*" in tok or "?" in tok or tok.lower() in NON_FILE_WORDS:
                continue
            if "/" in tok or tok.endswith(EXTENSIONS):
                out.append(tok)
    return out


def classify(op: str, path_set: set[str], by_base: dict[str, list[str]], prefixes: set[str]):
    clean = op[2:] if op.startswith("./") else op
    clean = clean.replace("\\", "/")
    if OUT_OF_REPO.match(op) or re.match(r"^[A-Za-z]:[\\/]", clean):
        return "EXTERNAL", []
    if clean in path_set:
        return "RESOLVES", [clean]
    if (clean.rstrip("/") + "/") in prefixes:      # a tracked directory is not a file promise
        return "DIR_NOT_FILE", []
    if any(p.endswith(clean.rstrip("/") + "/") for p in prefixes):
        # a fragment naming a directory that exists somewhere in the tree (`frontend/src`) is a route,
        # not a lost file; counting it as GONE made a resolved proof look unverifiable
        return "DIR_NOT_FILE", []
    cands = by_base.get(pathlib.PurePosixPath(clean).name, [])
    if not cands:
        return "GONE", []
    if len(cands) == 1:
        return ("RESOLVES" if cands[0] == clean else "MOVED"), cands
    return "AMBIGUOUS", cands


def repoint(command: str, mapping: dict[str, str]) -> str:
    out = str(command)
    for stale, fresh in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
        out = re.sub(r"(?<![\w./-])" + re.escape(stale) + r"(?![\w-])",
                     fresh.replace("\\", "\\\\"), out)
    return out


def state_for(row_operands: list[dict], error_id: str) -> tuple[str, str]:
    if error_id in ADJUDICATED:
        adj = ADJUDICATED[error_id]
        state = adj["state"]
        if state == "REPOINTED_20261007" and not adj.get("map"):
            # an override may claim a re-point only if it actually names the path it chose
            state = "ADJUDICATED_BY_HAND"
        return state, adj["reason"]
    if not row_operands:
        return "NO_FILE_OPERAND_IN_COMMAND", "the command names no file operand to check"
    cats = {o["category"] for o in row_operands}
    if "EXTERNAL" in cats and "RESOLVES" not in cats:
        return ("OUT_OF_REPO_TARGET", "the command reads a live client home path, which is outside "
                                     "every checkout by design")
    if "AMBIGUOUS" in cats:
        return "ADJUDICATED_BY_HAND", "several tracked paths share the basename; not re-pointed"
    if "GONE" in cats:
        return "PATH_GONE", "no tracked file carries this basename"
    if "MOVED" in cats:
        return "REPOINTED_20261007", "same basename found at exactly one other tracked path"
    return "RESOLVES", "every operand resolves against git ls-files"


def build_indexes():
    paths = tracked_paths()
    by_base: dict[str, list[str]] = collections.defaultdict(list)
    for p in paths:
        by_base[pathlib.PurePosixPath(p).name].append(p)
    prefixes = {str(pathlib.PurePosixPath(p).parent) + "/" for p in paths}
    return set(paths), by_base, prefixes


def measure(entries: list[dict]):
    path_set, by_base, prefixes = build_indexes()
    rows, mapping, ambiguous, gone, external = [], {}, [], [], []
    for e in entries:
        command = str(e.get("regression_test") or "")
        per = []
        for op in operands(command):
            kind, cands = classify(op, path_set, by_base, prefixes)
            per.append({"operand": op, "category": kind, "candidates": cands[:5]})
            if kind == "MOVED":
                mapping[op] = cands[0]
            elif kind == "AMBIGUOUS":
                ambiguous.append({"errorId": e["error_id"], "operand": op, "candidates": cands[:5]})
            elif kind == "GONE":
                gone.append({"errorId": e["error_id"], "operand": op,
                             "statusAfter": e.get("status_after")})
            elif kind == "EXTERNAL":
                external.append({"errorId": e["error_id"], "operand": op})
        state, reason = state_for(per, e["error_id"])
        rows.append({"errorId": e["error_id"], "statusAfter": e.get("status_after"),
                     "hasFixedCommit": bool((e.get("lifecycle") or {}).get("fixedCommit")),
                     "command": command[:200], "operands": per, "state": state, "reason": reason})
    return rows, mapping, ambiguous, gone, external


def next_reason(previous_state: object, previous_reason: object, state: str, measured_reason: str) -> str:
    """Keep a hand-authored explanation while the label it explains is unchanged; replace it when it moved.

    One sentence per label is what `state_for` can measure, so an unconditional write turns a record's
    specific reason into boilerplate. Measured 2026-10-08: publishing the audit for one new record rewrote
    three hand-authored reasons -- ERR-215's plus two older ones -- into "every operand resolves against
    git ls-files". Data that a re-run of the auditing tool destroys is not documentation, and the tool is
    re-run every time a record is added. A reason that still describes the label it sits under is not
    stale, so it survives; a label that changed must carry the reason it was measured with, because the old
    sentence explains a state the record no longer claims.
    """
    if previous_state == state and isinstance(previous_reason, str) and previous_reason.strip():
        return previous_reason
    return measured_reason


def apply_labels(data: dict) -> dict:
    """Rewrite commands, then stamp labels from the bytes that were actually written.

    A substitution that matched nothing must never be reported as a re-point, so the ledger is written
    and re-read before any label is chosen.
    """
    errors = data["errors"]
    _, mapping, _, _, _ = measure(errors)
    applied = dict(mapping)          # what was substituted; a later measure finds nothing MOVED
    for e in errors:
        command = str(e.get("regression_test") or "")
        hand = (ADJUDICATED.get(e["error_id"]) or {}).get("map") or {}
        new_command = repoint(command, {**mapping, **hand})
        if new_command != command:
            e["regression_test"] = new_command
            e["regressionRepointNote"] = (
                "operand re-pointed 2026-10-07 by scripts/audit/ledger_regression_command_targets.py: "
                "same basename, path changed by the 2026-09 module convergence; the command and what it "
                "tested are unchanged")
    LEDGER.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")

    written = json.loads(LEDGER.read_text(encoding="utf-8"))
    rows, _, _, _, _ = measure(written["errors"])
    for r in rows:
        rec = next(e for e in written["errors"] if e["error_id"] == r["errorId"])
        state = r["state"]
        if rec.get("regressionRepointNote"):
            # a hand-chosen re-point measures as its override state, not as RESOLVES, so both forms of
            # "the promise now points at tracked bytes" keep the claim; anything else has to disclaim it
            if state in ("RESOLVES", "REPOINTED_20261007"):
                state = "REPOINTED_20261007"
            else:
                rec["regressionRepointNote"] = (
                    "a substitution was attempted 2026-10-07 but the operand still does not resolve, "
                    "so no re-point is claimed and the promise stays where it was")
        # Read the label the record carried BEFORE this loop writes the measured one: line 260 below
        # overwrites the field, and comparing after that makes previous_state == state always true, so
        # the documented rule "a label that changed must carry the reason it was measured with" never
        # fires and a stale sentence keeps explaining a state the record no longer claims.
        prior_state = rec.get("regressionTestVerifiability")
        prior_reason = rec.get("regressionTestVerifiabilityReason")
        rec["regressionTestVerifiability"] = state
        rec["regressionTestVerifiabilityReason"] = next_reason(
            prior_state, prior_reason, state, r["reason"],
        )
    LEDGER.write_text(json.dumps(written, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")
    return json.loads(LEDGER.read_text(encoding="utf-8")), applied


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--audit-out", default=str(AUDIT))
    ap.add_argument("--json-out",
                    default=".project-local/runs/convergence-20261007-k/ledger_targets_detail.json")
    args = ap.parse_args()

    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    applied: dict[str, str] = {}
    if args.apply:
        data, applied = apply_labels(data)
    rows, mapping, ambiguous, gone, external = measure(data["errors"])
    # after an apply nothing measures as MOVED any more, so the map a reader must audit is the one that
    # was substituted, not the empty remainder — and it must survive a second run: a re-point history
    # that disappears when the tool is re-run is data loss, and the audit would then claim no re-points
    # ever happened while 34 records carry notes saying otherwise
    published_map = dict(applied or mapping)
    if AUDIT.is_file():
        try:
            prior = json.loads(AUDIT.read_text(encoding="utf-8")).get("repointMap") or {}
        except (json.JSONDecodeError, OSError):
            prior = {}
        for stale, fresh in prior.items():
            published_map.setdefault(stale, fresh)
    published_map = dict(sorted(published_map.items()))

    # `counts` publishes what the records CLAIM (their label), never what a fresh measurement happens to
    # say: a re-pointed promise measures as RESOLVES afterwards, and publishing the measure as the claim
    # would hide which records moved. Both numbers are published, each named for what it is.
    def label_of(error_id: str) -> str:
        rec = next(e for e in data["errors"] if e["error_id"] == error_id)
        return str(rec.get("regressionTestVerifiability") or "")

    counts = collections.Counter(label_of(r["errorId"]) or r["state"] for r in rows)
    measured = collections.Counter(r["state"] for r in rows)
    unlabelled = [e["error_id"] for e in data["errors"]
                  if str(e.get("regressionTestVerifiability") or "") not in STATES]
    labelled = [r for r in rows if label_of(r["errorId"]) == "REPOINTED_20261007"]
    digest = hashlib.sha256(json.dumps(sorted((r["errorId"], label_of(r["errorId"]) or r["state"])
                                              for r in rows),
                                       ensure_ascii=False).encode("utf-8")).hexdigest()
    detail = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "apply": bool(args.apply),
              "counts": dict(counts), "measuredStates": dict(measured),
              "repointMap": dict(sorted(published_map.items())),
              "ambiguous": ambiguous, "gone": gone, "external": external, "rows": rows,
              "unlabelled": unlabelled}
    out_detail = REPO / args.json_out
    out_detail.parent.mkdir(parents=True, exist_ok=True)
    out_detail.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")

    audit = {"schemaVersion": "work-lab/ledger-regression-command-targets/v3",
             "at": detail["at"],
             "tool": "scripts/audit/ledger_regression_command_targets.py",
             "scope": ("every record in taskpacks/current/error-ledger.json; file operands are extracted "
                       "from the `regression_test` COMMAND and matched against `git ls-files` only, so the "
                       "verdict cannot move with local disk state (ERR-142). Patterns, bare words, flags "
                       "and env assignments are not treated as file promises."),
             "states": list(STATES),
             "rules": {
                 "anchored substitution": "a stale operand is replaced only when the whole token "
                                          "matches, never inside a longer path (ERR-135)",
                 "no status rewrite": "status_after is never changed here; an unverifiable promise is "
                                      "labelled, not downgraded and not trusted",
                 "repoint basis": "only an unambiguous same-basename hit at exactly one other tracked "
                                  "path is re-pointed, and a re-point is claimed only when the written "
                                  "command then resolves",
                 "out-of-repo targets": "operands addressing a managed client's home (a drive path, ~/ "
                                        "or a $CODEX_HOME-style prefix) are claims about the live "
                                        "machine, not broken pointers into this repository"},
             "handAdjudicated": {k: {kk: vv for kk, vv in v.items() if kk != "map"}
                                 for k, v in ADJUDICATED.items()},
             "handRepointMaps": {k: v["map"] for k, v in ADJUDICATED.items() if v.get("map")},
             "counts": dict(counts),
             "measuredStates": dict(measured),
             "resolvedAfterApply": sum(1 for r in rows if r["state"] == "RESOLVES"),
             "records": len(rows), "stateDigest": digest,
             "repointMap": dict(sorted(published_map.items())),
             "ambiguous": ambiguous, "gone": gone, "external": external,
             "unlabelled": unlabelled, "apply": bool(args.apply), "rows": rows,
             "notClaimed": [
                 "a PATH_GONE label is not evidence the fix was wrong — only that this repository no "
                 "longer holds the file the promise names",
                 "re-pointing changes a path string, not what the original command tested",
                 "commands with no file operand are not verified here at all; they are counted and named "
                 "so the count stays visible",
                 "OUT_OF_REPO_TARGET claims are re-checkable only on the machine holding the live client "
                 "home, which is why they are labelled instead of counted as resolved",
                 "no record's status_after was changed by this tool"],
             "whyItMatters": ("the ledger carries " + str(sum(1 for e in data['errors']
                                                              if e.get('status_after') == 'PASS')) +
                              " PASS records; a promise whose file no longer exists cannot be re-run, so "
                              "each record now says which of the six states it is in")}
    out = pathlib.Path(args.audit_out)
    out.write_bytes(json.dumps(audit, ensure_ascii=False, indent=2).replace("\n", "\r\n").encode())

    print(f"records={len(rows)} labels={dict(counts)} measured={dict(measured)} repoints={len(mapping)} "
          f"repointClaimed={len(labelled)} ambiguousRaw={len(ambiguous)} "
          f"unadjudicatedAmbiguity={counts.get('ADJUDICATED_BY_HAND', 0)} gone={len(gone)} "
          f"external={len(external)} unlabelled={len(unlabelled)} apply={args.apply}")
    print(f"audit -> {out.relative_to(REPO).as_posix()}")
    print(f"detail -> {out_detail.relative_to(REPO).as_posix()}")
    if args.apply and unlabelled:
        return 1
    # an ambiguity a hand adjudication explains is not a failure; one nobody has looked at is, so the
    # signal is the labelled state and never the raw matcher count
    return 1 if counts.get("ADJUDICATED_BY_HAND", 0) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
