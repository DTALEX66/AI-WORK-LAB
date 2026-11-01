"""Read-only PR review preflight. Unknown required checks fail closed."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from github_common import ROOT, MANAGED_REPOS, request, redact


def _run_local_gate(repo: str) -> dict:
    if repo != "DTALEX66/WORK-LAB":
        return {"applicable": False}
    script = ROOT / "services/orchestration/run_quality_gate.py"
    try:
        r = subprocess.run([sys.executable, str(script), "verify"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        return {"applicable": True, "passed": r.returncode == 0 and
                "QUALITY_GATE_PASS" in r.stdout, "exit_code": r.returncode}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"applicable": True, "passed": False, "error": redact(str(exc))}


def _required_checks(repo: str, base: str) -> set[str]:
    required = set()
    for page in range(1, 101):
        rules = request("GET", f"/rules/branches/{base}?per_page=100&page={page}", repo=repo)
        if not isinstance(rules, list):
            raise RuntimeError("branch rules response was not a list")
        for rule in rules:
            if rule.get("type") == "required_status_checks":
                for item in rule.get("parameters", {}).get("required_status_checks", []):
                    if item.get("context"):
                        required.add(item["context"])
        if len(rules) < 100:
            break
    else:
        raise RuntimeError("branch rules pagination limit reached")
    try:
        protection = request("GET", f"/branches/{base}/protection/required_status_checks", repo=repo)
        required.update(c["context"] for c in protection.get("checks", []) if c.get("context"))
        required.update(protection.get("contexts", []))
    except RuntimeError as exc:
        # A ruleset may be available while the legacy protection endpoint is not.
        if not required:
            raise RuntimeError("required check policy cannot be confirmed") from exc
    if not required:
        raise RuntimeError("no required checks could be confirmed")
    return required


def _all_check_runs(repo: str, sha: str) -> dict[str, str]:
    found = {}
    for page in range(1, 101):
        data = request("GET", f"/commits/{sha}/check-runs?per_page=100&page={page}", repo=repo)
        rows = data.get("check_runs")
        if not isinstance(rows, list):
            raise RuntimeError("check-runs response is incomplete")
        for row in rows:
            if row.get("head_sha") not in (None, sha):
                raise RuntimeError("check run SHA differs from PR head")
            name = row.get("name")
            if name:
                state = row.get("conclusion") if row.get("status") == "completed" else row.get("status")
                # Push and PR suites can emit the same context for one SHA.
                # A successful duplicate must not hide a pending or failed run.
                if name not in found or found[name] == "success":
                    found[name] = state
        if len(rows) < 100:
            return found
    raise RuntimeError("check-runs pagination limit reached")


def review(repo: str, pr_number: int, local_gate: bool = True) -> dict:
    result = {"repo": repo, "pr": pr_number, "recommendation": "UNKNOWN", "reasons": []}
    try:
        if repo not in {e["repo"] for e in MANAGED_REPOS}:
            raise ValueError("repository is not registered")
        pr = request("GET", f"/pulls/{pr_number}", repo=repo)
        sha = pr["head"]["sha"]
        base = pr["base"]["ref"]
        required = _required_checks(repo, base)
        statuses = _all_check_runs(repo, sha)
        result.update(head_sha=sha, required_checks=sorted(required), checks=statuses,
                      mergeable=pr.get("mergeable"), mergeable_state=pr.get("mergeable_state"))
        bad = {name: statuses.get(name, "missing") for name in required if statuses.get(name) != "success"}
        if bad:
            result["reasons"].append(f"required checks not successful: {bad}")
        if pr.get("mergeable") is not True or pr.get("mergeable_state") != "clean":
            result["reasons"].append("PR mergeability is not clean")
        local = _run_local_gate(repo) if local_gate else {"applicable": False}
        result["local_gate"] = local
        if local.get("applicable") and not local.get("passed"):
            result["reasons"].append("local quality gate failed")
        result["recommendation"] = "APPROVE" if not result["reasons"] else "BLOCK"
    except (RuntimeError, ValueError, KeyError, TypeError) as exc:
        result["reasons"].append(redact(str(exc)))
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="GitHub review preflight")
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--no-local-gate", action="store_true")
    args = p.parse_args(argv)
    result = review(args.repo, args.pr, local_gate=not args.no_local_gate)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["recommendation"] == "APPROVE" else 1


if __name__ == "__main__":
    sys.exit(main())
