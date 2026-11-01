#!/usr/bin/env python3
"""Fail-closed validation for the sanitized WORK-LAB error ledger."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

LEDGER_REL = Path("taskpacks/current/error-ledger.json")
ALLOWED_PHASES = {
    "AUDIT_ONLY",
    "PLAN",
    "LOCAL_IMPLEMENTATION",
    "LOCAL_VERIFICATION",
    "EVIDENCE_CLOSEOUT",
}
ALLOWED_EVIDENCE = {"local-focused", "local-full", "isolated-runtime", "historical"}
ALLOWED_STATUS = {"NOT_RUN", "FAIL", "UNVERIFIED", "PASS", "PARTIAL", "BLOCKED"}
REQUIRED = {
    "error_id", "task_id", "phase", "classification", "entrypoint", "command",
    "exit_code", "observed_error", "root_cause", "fix", "regression_test",
    "evidence_level", "repeat_prevention", "remaining_boundary", "status_before", "status_after",
}
SECRET_PATTERNS = (
    re.compile(r"(?:api[_-]?key|secret|password|authorization|cookie|private[_-]?key)\s*[:=]", re.I),
    re.compile(r"\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}", re.I),
    re.compile(r"\b(?:sk-|gh[pousr]_|xox[baprs]-)[A-Za-z0-9_-]{8,}", re.I),
)


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists() and (parent / "services").is_dir():
            return parent
    raise SystemExit("ERROR_LEDGER_FAIL cannot locate WORK-LAB root")


def fail(message: str) -> int:
    print(f"ERROR_LEDGER_FAIL {message}")
    return 1


def walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_strings(child)


def main() -> int:
    # `--ledger <path>` exists so the gate can be pointed at a synthetic ledger and PROVED to fire.
    # Without it, every claim about what this verifier refuses rests on the real file being healthy,
    # which is not evidence that the check works -- my first falsification attempt today passed for
    # exactly this reason: it wrote a bad copy and the verifier read the good one.
    argv = sys.argv[1:]
    path = repo_root() / LEDGER_REL
    if "--ledger" in argv:
        index = argv.index("--ledger")
        if index + 1 >= len(argv):
            return fail("--ledger requires a path")
        path = Path(argv[index + 1])
    if not path.is_file():
        return fail(f"missing {LEDGER_REL.as_posix()}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return fail(f"invalid JSON: {exc}")
    if data.get("schema_version") != "work-lab/error-ledger/v1":
        return fail("unsupported schema_version")
    if not isinstance(data.get("errors"), list) or not data["errors"]:
        return fail("errors must be a non-empty list")
    privacy = data.get("privacy")
    if not isinstance(privacy, dict) or any(privacy.get(key) is not False for key in (
        "raw_credentials_included", "raw_logs_included", "prompt_response_bodies_included"
    )):
        return fail("privacy flags must explicitly be false")

    errors = data["errors"]
    ids: list[str] = []
    classifications: Counter[str] = Counter()
    for index, item in enumerate(errors):
        if not isinstance(item, dict):
            return fail(f"errors[{index}] must be an object")
        missing = sorted(REQUIRED - set(item))
        if missing:
            return fail(f"errors[{index}] missing {','.join(missing)}")
        error_id = item["error_id"]
        if not isinstance(error_id, str) or not re.fullmatch(r"ERR-[0-9]{3}", error_id):
            return fail(f"errors[{index}] invalid error_id")
        ids.append(error_id)
        if item["phase"] not in ALLOWED_PHASES:
            return fail(f"{error_id} invalid phase")
        if item["evidence_level"] not in ALLOWED_EVIDENCE:
            return fail(f"{error_id} invalid evidence_level")
        if item["status_before"] not in ALLOWED_STATUS or item["status_after"] not in ALLOWED_STATUS:
            return fail(f"{error_id} invalid status")
        if not isinstance(item["exit_code"], int):
            return fail(f"{error_id} exit_code must be int")
        for key in REQUIRED - {"exit_code"}:
            if not isinstance(item[key], str) or not item[key].strip():
                return fail(f"{error_id} {key} must be non-empty text")
        if item["exit_code"] == 0:
            return fail(f"{error_id} original failure exit_code cannot be zero")
        if not re.search(r"(?:python|node|git|assessment|test|verify)", item["command"], re.I):
            return fail(f"{error_id} command is not an executable record")
        for field in ("introducedCommit", "fixedCommit", "verifiedCommit"):
            value = (item.get("lifecycle") or {}).get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            if not re.fullmatch(r"[0-9a-f]{40}", value):
                return fail(f"{error_id} {field} must be a full 40-hex commit or null, "
                            f"got {value[:24]!r}")
        if not any(token in item["repeat_prevention"].lower() for token in ("must", "require", "never", "每", "必须")):
            return fail(f"{error_id} repeat_prevention is not enforceable")
        for value in walk_strings(item):
            if any(pattern.search(value) for pattern in SECRET_PATTERNS):
                return fail(f"{error_id} contains a credential-like value")
        classifications[item["classification"]] += 1

    if len(ids) != len(set(ids)):
        return fail("duplicate error_id")
    summary = data.get("summary")
    if not isinstance(summary, dict) or summary.get("total") != len(errors):
        return fail("summary.total does not match errors length")
    if summary.get("by_classification") != dict(classifications):
        return fail("summary.by_classification does not match ledger rows")
    if summary.get("repeat_prevention_required") is not True:
        return fail("repeat_prevention_required must be true")
    print(
        "ERROR_LEDGER_PASS "
        f"entries={len(errors)} classifications={len(classifications)} "
        "raw_sensitive_data=false counts_consistent=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
