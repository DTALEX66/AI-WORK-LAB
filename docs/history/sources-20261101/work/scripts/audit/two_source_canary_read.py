"""Read the two authorized canary sources and publish the receipt with its own subject.

WUI-18's first acceptance clause is "positive read from the two authorized sources". The authority for
which sources those are is `config/canary-config.json` (`mode: READ_ONLY`, every row `user-approved` and
`readOnly: true`), so this instrument takes its roots from that file instead of a command line, refuses a
row that does not declare both flags, and never reads project content -- only git metadata, which is what
`services/orchestration/canary_runner.py` is documented to do for an external root.

A positive read here has two different shapes, and the report keeps them apart:
  * WORK-LAB resolves to its own project id (the identity chain works);
  * the external OS project must come back UNRESOLVED -- resolving it into work-lab would be a false merge,
    which is the failure this canary exists to catch.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "config" / "canary-config.json"
ARTIFACT = REPO / ".project-local" / "artifacts" / "wui-20261010" / "two-source-canary-read.json"
RUNNER = REPO / "services/orchestration/canary_runner.py"


def boot_batch_import_path() -> None:
    """The canary imports sibling modules the same way the governance batch does."""
    sys.path.insert(0, str(REPO / "services" / "orchestration"))
    import run_quality_gate as batch

    for entry in reversed(batch.MODULE_PYTHONPATH.split(os.pathsep)):
        if entry and entry not in sys.path:
            sys.path.insert(0, entry)


def approved_roots() -> list[str]:
    declared = json.loads(CONFIG.read_text(encoding="utf-8"))
    if declared.get("mode") != "READ_ONLY":
        raise RuntimeError(f"CANARY_MODE_NOT_READ_ONLY {declared.get('mode')!r}")
    rows = declared["workspaceAllowlist"]
    roots: list[str] = []
    for row in rows:
        if row.get("approval") != "user-approved" or row.get("readOnly") is not True:
            raise RuntimeError(f"CANARY_ROOT_NOT_AUTHORISED {row.get('path')} {row}")
        roots.append(row["path"])
    if len(roots) < 2:
        raise RuntimeError(f"CANARY_NEEDS_TWO_SOURCES roots={len(roots)}")
    return roots


def git_facts(root: Path) -> dict[str, object]:
    def run(*args: str) -> str | None:
        try:
            done = subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        return done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else None

    porcelain = run("status", "--porcelain=v1")
    return {
        "head": run("rev-parse", "HEAD"),
        "branch": run("branch", "--show-current") or "detached",
        "dirtyEntries": None if porcelain is None else len([l for l in porcelain.splitlines() if l.strip()]),
        "unreadable": porcelain is None,
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    roots = approved_roots()
    missing = [r for r in roots if not Path(r).is_dir()]
    if missing:
        print("TWO_SOURCE_CANARY_READ FAIL (declared roots not on disk)", missing)
        return 2

    boot_batch_import_path()
    os.environ["WORKLAB_CANARY_PROJECT_ROOTS"] = os.pathsep.join(roots)
    import canary_runner

    report = canary_runner.run_canary()
    per_root = {root: git_facts(Path(root)) for root in roots}
    external = report["external_canary"]["roots"]
    self_ok = bool(report.get("self_root_resolved"))
    # Each authorized root answers a different question, and both answers are positive reads:
    # this repository must resolve to its own project id, while an external OS project must come back
    # UNRESOLVED. Treating the second rule as if it applied to the first would call a correct identity
    # read a failure -- which is exactly what this instrument did on its first run.
    answers: list[dict[str, object]] = []
    for row in external:
        is_self = Path(str(row["root"])).resolve() == REPO.resolve()
        want = "RESOLVED" if is_self else "UNRESOLVED"
        answers.append({
            "root": row["root"],
            "isThisRepository": is_self,
            "expectedState": want,
            "observedState": row.get("resolutionState"),
            "projectId": row.get("projectId"),
            "ok": row.get("resolutionState") == want and (row.get("projectId") == "work-lab" if is_self
                                                          else row.get("projectId") is None),
        })
    roots_ok = bool(answers) and all(row["ok"] for row in answers)

    verdict = "PASS" if (self_ok and roots_ok and report.get("all_pass")) else "FAIL"
    receipt = {
        "schemaVersion": "worklab/two-source-canary-read/v1",
        "observedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "subject": {
            "repoHead": git_facts(REPO)["head"],
            "repoTree": subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=REPO, capture_output=True)
            .stdout.decode().strip(),
            "canaryConfigSha256": sha(CONFIG),
            "canaryRunnerSha256": sha(RUNNER),
        },
        "sources": {
            "declaredIn": CONFIG.relative_to(REPO).as_posix(),
            "roots": roots,
            "gitMetadataPerRoot": per_root,
            "contentRead": False,
        },
        "canaryReport": report,
        "answers": {
            "selfRootResolved": self_ok,
            "perRoot": answers,
            "allRootsAnswered": roots_ok,
            "externalExpectedState": "UNRESOLVED (resolving an approved external project into work-lab "
                                     "would be a false merge)",
        },
        "verdict": verdict,
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"TWO_SOURCE_CANARY_READ {verdict} roots={len(roots)} self_resolved={self_ok} "
          f"all_roots_answered={roots_ok} all_pass={report.get('all_pass')}")
    for row in answers:
        print(f"  root={row['root']} expected={row['expectedState']} observed={row['observedState']} "
              f"projectId={row['projectId']} ok={row['ok']}")
    print(f"  receipt={ARTIFACT.relative_to(REPO).as_posix()}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
