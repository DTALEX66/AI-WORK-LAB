"""Audit every tracked-document citation of a `.project-local` path and classify the absent ones.

Why this exists: `docs/audits/RELEASED_BROWSER_STATE_2026-10-07.json` recorded "28 tracked documents
cite `.project-local` paths that no longer exist" from one narrow scan. A full-tree scan gives 200
absent tokens, so the number is an artefact of the scanner's scope, not a count of broken promises.
The only thing that matters is whether a record claims *evidence is available here* while the file
is gone, so this script separates the real class from the four decoy classes and writes a durable,
re-runnable answer.

Read-only. Usage:
    python scripts/audit/project_local_citation_audit.py [--out docs/audits/...json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = "docs/audits/PROJECT_LOCAL_CITATION_AUDIT_2026-10-07.json"

TOKEN_RE = re.compile(r"\.project-local/[A-Za-z0-9_\-./\u4e00-\u9fff]*")
TRAILING = ".,;:!?)]}\"'`"
PATTERN = re.compile(r"(\.\.|XX|x{4}|\*|\{|\}|<|\+|\bYYYY\b|\b202X\b)")
TRUNCATED = re.compile(r"[-_]$")
NEGATIVE = re.compile(
    r"(must not|not exist|never|forbidden|ignore|absent|refuse|reject|does not exist|no longer|"
    r"deleted|removed|cleanup|exclude|excluded|shall not|do not create|must be absent|"
    r"不存在|禁止|不应|已删除)", re.I)
# A machine field whose value is a path is either evidence or a declared destination; the field
# name decides which, and only the evidence-shaped names are treated as a claim that bytes exist.
EVIDENCE_FIELD = re.compile(r'"(evidence[A-Za-z]*|receipt[A-Za-z]*|artifact[A-Za-z]*|proofPath|'
                            r'reportPath|sourcePath|outputPath)"\s*:\s*"[^"]*\.project-local/')
# In code, a `.project-local` string literal is a location the program will create or a fixture it
# invents; in a shell command it is an --output/--write-template target. Neither cites evidence.
CODE_SUFFIX = (".py", ".sh", ".ps1", ".cmd", ".js", ".mjs", ".ts")
DEST_IN_SHELL_ARG = re.compile(r"(--output|--write-template|--dir|--root|--cache-dir|>\s*)\s*"
                               r"[\"']?[^\s\"']*\.project-local/")
VERB_CITING_EVIDENCE = re.compile(r"(see |at |per |recorded in|captured in|stored in|written to|"
                                  r"evidence is|receipt is|proof:|full output in|日志|见 |存于|证据在)",
                                  re.I)
FROZEN = re.compile(r"^(docs/history/|docs/audits/|taskpacks/archive|.*archive/)")
# A register row, handoff note or report that names a runtime path is narration about bytes its author
# produced, not a pointer a reader has to be able to open. `.project-local/` is the declared
# git-ignored runtime root, so those paths exist on exactly one machine by design; judging them from
# local disk state made the verdict machine-dependent and turned CI red on the author's own tooling
# (ERR-142).
NARRATION_ROOTS = re.compile(r"^(taskpacks/|reports/|docs/history/|docs/audits/|.*archive/)")
# Reader-facing entry points are the places where a sentence can actually send someone to bytes.
READER_FACING = re.compile(r"^(README.md|docs/current/|config/|docs/decisions/|apps/observer/README.md)")


def tracked_files() -> list[str]:
    raw = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "-z"],
                         cwd=REPO, capture_output=True).stdout.split(b"\0")
    return [p.decode("utf-8", "replace") for p in raw if p]


def looks_like_file(token: str) -> bool:
    return re.search(r"\.[A-Za-z0-9]{1,8}$", token) is not None


def exists(rel: str) -> bool:
    """Is this token's bytes verifiable from the repository itself?

    `.project-local/` is the git-ignored runtime root by declaration, so nothing under it can ever be
    checked out: answering from the local disk made the verdict machine-dependent, and CI failed on
    `.project-local/toolchains/…` paths that exist on the author's box and nowhere else (ERR-142). A
    citation into that root is therefore treated as not-verifiable-here on every machine, so the
    verdict is the same in a clean checkout as on the box that produced the bytes.
    """
    if PurePosixPath(rel).parts[:1] == (".project-local",):
        return False
    p = REPO / PurePosixPath(rel)
    return p.is_file() if looks_like_file(rel) else p.exists()


def exists_on_this_machine(rel: str) -> bool:
    """Raw disk state, reported separately so the record does not pretend nothing is there."""
    p = REPO / PurePosixPath(rel)
    return p.is_file() if looks_like_file(rel) else p.exists()


def classify(token: str, file: str, line: str) -> str:
    leaf = token.split("/")[-1]
    if PATTERN.search(leaf) or TRUNCATED.search(leaf):
        return "path_pattern_or_truncated_token"
    if NEGATIVE.search(line):
        return "negative_assertion_or_removal_record"
    if (file.endswith(CODE_SUFFIX) or DEST_IN_SHELL_ARG.search(line)) \
            and not VERB_CITING_EVIDENCE.search(line):
        return "declared_output_destination_or_fixture_in_code"
    if EVIDENCE_FIELD.search(line):
        return "machine_field_pointing_at_absent_path"
    if token.startswith(".project-local/") and NARRATION_ROOTS.match(file):
        return "machine_local_runtime_narration"
    if token.startswith(".project-local/"):
        # A pointer into the declared runtime root is only a promise worth chasing when a reader-facing
        # document actually tells someone to open those bytes. Everywhere else it is bookkeeping about
        # machine-local state, and CI cannot see that state by design — so the class is stated rather
        # than left to be adjudicated path by path (ERR-142).
        if not (READER_FACING.match(file) and VERB_CITING_EVIDENCE.search(line)):
            return "machine_local_runtime_pointer"
    if FROZEN.match(file):
        return "prose_in_frozen_history_or_audit"
    return "unclassified_needs_human_read"


# Hand-adjudicated disposition for every path that survives classification as a possible
# unavailable-evidence claim. A queue entry with no disposition prints as UNADJUDICATED, which is
# the state this table exists to eliminate.
DISPOSITIONS: dict[str, str] = {
    # Measured 2026-10-10: the directory exists and holds exactly `node-jiti/frontend-tailwind.config.js
    # .a24e14cf.js` (a loader cache) and `outside-context.txt` (a test scratch file a guard wrote). The
    # citations naming it are historical -- the error ledger and the cutover record both recount the round
    # that moved TMP/TEMP binding off this path -- so the row is kept, and what is left here is residue
    # for an audited cleanup, not evidence a reader owes.
    ".project-local/runs/tmp":
        "HISTORICAL ROUND + RESIDUE — the path is the old bound temp root the gate no longer uses; the two "
        "files still on disk are a jiti loader cache and a scratch fixture, and deleting them is a separate "
        "audited cleanup (prove recoverability first), not something a citation may assume.",
    ".project-local":
        "DECLARED ROOT — `.project/governance/project-data-boundary.json` names it as the runtime and "
        "evidence root every sanctioned writer targets. A directory declaration is not evidence a "
        "reader has to open, and it is git-ignored by design, so CI never sees it and is not asked to.",
    ".project-local/artifacts":
        "DECLARED ROOT — `taskArtifactsRoot`/`canonicalEvidenceRoot` in the boundary declaration; the "
        "citations name where sanctioned tools write, not bytes a reader must recover.",
    ".project-local/runs":
        "DECLARED ROOT — `runtimeRoot`/`logsRoot`/`cacheRoot` in the boundary declaration; the citations "
        "describe where run logs and receipts land.",
    ".project-local/artifacts/model-library-readback.json":
        "MACHINE-LOCAL RECEIPT WITH A RE-MEASURE COMMAND — `.project/governance/model-registry.json` "
        "quotes it as '(machine-local receipt; regenerate with: python scripts/audit/"
        "model_library_readback.py)', the regenerator is tracked, and a tracked counterpart exists at "
        "`docs/audits/MODEL_LIBRARY_READBACK_2026-10-07.md`. The file was present on the authoring box "
        "(14,754 B, 2026-10-07). CI is not asked to believe the bytes — only to see that the claim "
        "names how to reproduce them.",
    ".project-local/artifacts/cl07/receipt.json":
        "MACHINE-LOCAL RENDER RECEIPT NAMED AS WHAT WAS OBSERVED — the CL-07 probe wrote it on the "
        "authoring box (verdict=PASS, 12/12 checks, screenshot beside it); the tracked test "
        "`apps/observer/frontend/src/views/IssueCenter.test.tsx` covers the same handoff behavior "
        "without a browser, and the convergence record cites the receipt only for the measured "
        "clipboard bytes. CI is not asked to recover this file.",
    ".project-local/runs/u19-msvc-20261006/target/release/app.exe":
        "MACHINE-LOCAL BUILD OUTPUT NAMED AS WHAT WAS RUN — the desktop readback records "
        "(`docs/audits/RELEASED_BROWSER_STATE_2026-10-07.json`, "
        "`docs/future/WORK-LAB-BLUEPRINT-COVERAGE.md`) cite the binary the owner actually launched. The "
        "readback claim rests on that recorded observation, not on this path existing on a runner, and "
        "the binary is regenerable from tracked source by the recorded cargo build.",
    ".project-local/runs/observer":
        "DESTINATION — `apps/observer/module-profile.json` declares where the read-only projection "
        "writes when it runs; nothing validates its existence and it has not been asked to run.",
    ".project-local/artifacts/current-state-ci.json":
        "DESTINATION — written by `scripts/ci/generate_current_state.py`; the register row names it "
        "as the producer side of a producer/consumer divergence that round D fixed.",
    ".project-local/artifacts/error-ledger-20260806.json":
        "FIXED 2026-10-07 — a current doc listed it under 'Canonical files', which told a reader to "
        "read a file that does not exist; re-pointed at `taskpacks/current/error-ledger.json` with a "
        "dated correction kept in place (ERR-131).",
    ".project-local/artifacts/evals":
        "DESTINATION — doc instruction to copy an eval template into the current project's own dir.",
    ".project-local/artifacts/mcp-candidate.yaml":
        "DESTINATION — created by `mcp_candidate_audit.py --write-template` in the documented "
        "usage examples; the input-side example assumes you ran the template step first.",
    ".project-local/artifacts/orca-pilot":
        "DESTINATION — the pilot card's declared data boundary (产物只落此处); the pilot never ran.",
    ".project-local/artifacts/wl3-810-archive/migration-20260805/source-checkouts-archive-manifest.json":
        "HISTORICAL POINTER, bytes gone with the 2026-08-10 archive retirement. The same file records "
        "the retirement and the surviving root `docs/history/archive-manifests/migration-20260805/`; "
        "the field is named `legacy*`, so it states where it was, not where it is. Not edited.",
    ".project-local/kanban":
        "DESTINATION — one of the cache/TMP roots the guarded executor redirects to "
        "`<project>/.project-local/…` before launching a child process.",
    ".project-local/runs/ci/changed-paths.txt":
        "DESTINATION — the runner writes it and passes it with `--changed-path-file`; it exists only "
        "during a CI run.",
    ".project-local/runs/deepseek-harness":
        "SUPERSEDED LAYOUT — the adapter doc names it explicitly as the legacy isolated-checkout "
        "layout, i.e. the thing that is no longer used.",
    ".project-local/runs/frontend-baseline-vitest-only.py":
        "ALREADY RECORDED AS DANGLING — `config/skill-provenance.yaml` states that the live lesson's "
        "dangling citation to this ephemeral path was removed; the register row cites it historically.",
    ".project-local/runs/p0c-diag-20261006":
        "RE-POINTED 2026-10-07 — the bytes survive inside the WorkBuddy worktree import at "
        "`imported-from-workbuddy-20261006/WORK-LAB__task-decomposition-atlas-gap-archive-20261001-"
        "381e33ec/.project-local/runs/p0c-diag-20261006/` (per-file sha256: onlySrc=0, onlyDst=0, "
        "contentDiff=0). `SESSION-HANDOFF-P0C-20261006.md` now says to read the import path.",
    ".project-local/runs/skill-call-index.json":
        "DESTINATION — the per-project skill-call index the global execution standard tells a reader "
        "to consult when it has been built.",
    ".project-local/sleep-mode":
        "DESTINATION — state root the sleep-mode feature writes; the feature is not scheduled here.",
    ".project-local/sleep-mode/activity.jsonl":
        "DESTINATION — sleep-mode's own state-transition log, read when the feature has run.",
    ".project-local/sleep-mode/state.json":
        "DESTINATION — sleep-mode's mode/job_id/baseline state file, read when the feature has run.",
    # --- 2026-10-07: five scratch originals released after their tracked promotions survived a
    #     full cycle, plus one fixture inside this instrument's own gate
    ".project-local/runs/convergence-20261007-c/absorb_local_assets.py":
        "RELEASED 2026-10-07 as a redundant scratch original — the tracked copy "
        "`scripts/maintenance/absorb_local_assets.py` has the identical sha256 "
        "(docs/audits/SCRATCH_PROMOTION_REDUNDANCY_2026-10-07.json). Cited only in ledger `command` "
        "fields, which are history; the live promise points at the tracked path (ERR-130).",
    ".project-local/runs/convergence-20261007-c/cdp_layout_probe.mjs":
        "RELEASED 2026-10-07 — identical sha256 to the tracked `scripts/audit/cdp_layout_probe.mjs`; "
        "cited from ledger history and round C's handoff narrative.",
    ".project-local/runs/convergence-20261007-c/falsify_browser_entry.py":
        "RELEASED 2026-10-07 — identical sha256 to the tracked "
        "`scripts/audit/falsify_browser_entry.py`; cited only in ledger `command`/`regression_test` "
        "history.",
    ".project-local/runs/convergence-20261007-c/mutation_probe_pathspec.py":
        "RELEASED 2026-10-07 — identical sha256 to the tracked "
        "`scripts/audit/mutation_probe_pathspec.py`; cited only in ledger history.",
    ".project-local/runs/convergence-20261007-e/release_browser_state.py":
        "RELEASED 2026-10-07 — identical sha256 to the tracked `scripts/maintenance/"
        "release_browser_state.py`, the tool that freed the 116,216,094 B of browser state in "
        "round E; cited only in ledger history.",
    ".project-local/runs/x/receipt.json":
        "TEST FIXTURE, not a citation — the path appears only inside this instrument's own negative "
        "controls in tests/workflow-assistance/test_project_local_citation_audit.py, which feed the "
        "classifier an evidence-shaped sentence and a destination-shaped sentence. A fictional path "
        "used to prove a matcher works is not a broken promise.",
    # --- 2026-10-10: this round's SSE readback, added when DESIGN.md and the two UI-V2 rows began citing it
    ".project-local/artifacts/wui-20261009/sse-revision.json":
        "MACHINE-LOCAL READBACK WITH A RE-MEASURE COMMAND — produced by the tracked instrument "
        "`scripts/audit/sse_revision_via_cdp.py`, which writes exactly this path (its default `OUT_DIR`) "
        "and prints `SSE_REVISION_GATE_PASS` / `_FAIL` as its own verdict. Re-measure with "
        "`python scripts/audit/sse_revision_via_cdp.py`; the falsification run the register cites is "
        "`--revisions 7,9,10`, which must exit 1. Present on the authoring box as of 2026-10-10 "
        "(2,591 B, sha256 578d6a8f9388f242…, its verdict token reads `SSE_REVISION_GATE_PASS`, "
        "`failures` is empty, `revisionsPushed` is `[7, 9, 8]`, and `reconnectLastEventIds` is empty — "
        "the empty cursor list is the "
        "honest record that this stream never disconnected, so the `Last-Event-ID` branch was covered "
        "elsewhere instead of being claimed here). The reader-facing citations (`apps/observer/frontend/"
        "DESIGN.md`, `taskpacks/current/OPEN-TASK-REGISTER.md` WUI-14/WUI-15, the two UI-V2 CSVs) quote "
        "the observation that was made, not bytes a checkout must supply; `.project-local/` is "
        "git-ignored by declaration, so CI is asked to see the re-measure command, never to believe the "
        "receipt.",
    ".project-local/artifacts/wui-20261009/refs-census-20261018.json":
        "MACHINE-LOCAL CENSUS FROM AN UNTRACKED DRIVER — 889,298 B, sha256 024d34786ef9feef…, written "
        "2026-10-18T17:21:26Z at head 0369d349d46b75c7048b884331bb40a0f42d4e34. Its own `rule` field "
        "names the predicate it applied (`scripts/ci/verify_authority_index_paths.py:check()`) over 662 "
        "surfaces, and its totals are the claim: live 33 surfaces / 512 refs / 143 broken, dated_archive "
        "70 / 329 / 243, external_skill_copy 559 / 3,327 / 2,871. What is NOT in the tree is the driver "
        "that wrote it, so no re-measure command exists — and that absence is exactly what the two "
        "reader-facing sentences cite the path for, not the bytes. CI is asked to see the classification "
        "and the missing instrument, never to believe a receipt a checkout cannot supply "
        "(`.project-local/` is git-ignored by declaration). Adjudicated 2026-10-20; the open repair, if "
        "the owner wants it, is to land the census as a tracked instrument with its own gate.",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    hits: dict[str, list[dict]] = defaultdict(list)
    files_scanned = 0
    out_norm = os.path.normpath(str(REPO / args.out))
    for rel in tracked_files():
        if os.path.normpath(str(REPO / rel)) == out_norm:
            # never scan own output: the record quotes every token it found, and each citation it
            # stores carries the citing line, so reading itself back makes the file grow on every
            # regeneration (1.7 MB -> 3.7 MB in one re-run) instead of reporting a stable state
            continue
        ap_ = REPO / rel
        if not ap_.is_file():
            continue
        try:
            text = ap_.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files_scanned += 1
        for n, ln in enumerate(text.splitlines(), 1):
            for m in TOKEN_RE.finditer(ln):
                tok = m.group(0).rstrip(TRAILING).rstrip("/")
                if tok:
                    hits[tok].append({"file": rel, "line": n, "text": ln.strip()[:200]})

    present = sorted(t for t in hits if exists(t))
    absent = sorted(t for t in hits if not exists(t))
    buckets: dict[str, list[dict]] = defaultdict(list)
    for tok in absent:
        for c in hits[tok]:
            buckets[classify(tok, c["file"], c["text"])].append({"path": tok, **c})

    queue = sorted({r["path"] for k in ("machine_field_pointing_at_absent_path",
                                        "unclassified_needs_human_read")
                    for r in buckets.get(k, [])})
    doc = {
        "schemaVersion": "work-lab/project-local-citation-audit/v2",
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generatedBy": "scripts/audit/project_local_citation_audit.py",
        "scope": {"trackedFilesScanned": files_scanned,
                  "distinctProjectLocalTokens": len(hits),
                  "tokensResolvedOnDisk": len(present),
                  "tokensAbsent": len(absent),
                  "citationsToAbsentTokens": sum(len(hits[t]) for t in absent)},
        "classificationRules": {
            "path_pattern_or_truncated_token":
                "the token carries a placeholder, glob, or is cut mid-name; it never named one file",
            "negative_assertion_or_removal_record":
                "the sentence says the path must not exist, or records that it was removed",
            "declared_output_destination_or_fixture_in_code":
                "a script or command names a location it will create, or a synthetic fixture path; "
                "absence is the normal state and creating it unasked would be the spill",
            "machine_field_pointing_at_absent_path":
                "a machine-readable evidence/receipt/artifact field names an absent path",
            "prose_in_frozen_history_or_audit":
                "historical or audit narrative describing where files were at the time",
            "machine_local_runtime_pointer":
                "a tracked record names a path inside the declared git-ignored runtime root without "
                "telling a reader to open it. CI cannot see that root by design, so the class is "
                "declared here rather than adjudicated path by path (ERR-142)",
            "machine_local_runtime_narration":
                "a register row, handoff note or report describing which runtime paths its own run "
                "produced; narration about the authoring machine, not a pointer to follow",
            "unclassified_needs_human_read": "not auto-disposed; listed for a per-path decision",
        },
        "countsByClass": {k: {"citations": len(v), "distinctPaths": len({r['path'] for r in v})}
                          for k, v in sorted(buckets.items())},
        "buckets": {k: sorted(v, key=lambda r: (r["path"], r["file"], r["line"]))
                    for k, v in sorted(buckets.items())},
        "unavailableEvidenceReviewQueue": queue,
        "dispositions": {p: DISPOSITIONS.get(p, "UNADJUDICATED") for p in queue},
        "counts": {"reviewQueue": len(queue),
                   "unadjudicated": sum(1 for p in queue if p not in DISPOSITIONS),
                   "checkoutVerifiable": len(present),
                   "presentOnThisMachine": sum(1 for token in hits
                                               if exists_on_this_machine(token))},
        "disposition": (
            "Read the classes before quoting a number. Existence is answered from the repository, not "
            "from this box: `.project-local/` is the declared git-ignored runtime root, so nothing under "
            "it is checkout-verifiable anywhere and `counts.checkoutVerifiable` is 0 by construction, "
            "while `counts.presentOnThisMachine` reports how much the authoring machine actually holds. "
            "Before that rule the verdict moved with the machine and CI failed on the author's own "
            "runtime paths (ERR-142). The number that matters is unavailableEvidenceReviewQueue: "
            "citations in reader-facing documents or tracked machine fields that claim recoverable "
            "evidence while the bytes are not verifiable from the repository. Everything else is a "
            "pattern, a destination a program will create, a negative assertion, frozen narrative, or a "
            "declared machine-local runtime pointer/narration — all correct states, and deleting those "
            "records would destroy provenance rather than protect it. A machine-local citation counts as "
            "adjudicated only when the record says how to re-measure it or names the tracked observation "
            "that stands in for it; that is what the dispositions do, path by path."),
    }
    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2).replace("\n", "\r\n").encode())
    print(f"scanned={files_scanned} tokens={len(hits)} present={len(present)} absent={len(absent)}")
    for k, v in sorted(doc["countsByClass"].items()):
        print(f"  {v['citations']:>4} citations / {v['distinctPaths']:>3} paths  {k}")
    print(f"RESULT reviewQueue={len(queue)} unadjudicated={doc['counts']['unadjudicated']}")
    for p in queue:
        print(f"  {'UNADJUDICATED' if p not in DISPOSITIONS else 'DISPOSED'} {p}")
    print(f"audit -> {args.out} ({out.stat().st_size} bytes)")
    return 1 if doc["counts"]["unadjudicated"] else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
