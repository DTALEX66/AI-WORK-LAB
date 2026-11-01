#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Host E3 evidence verifier (Batch F-4) — fail-closed, stdlib only, no network.

An E3 claim is a claim that a *real host* (Adobe Photoshop/Illustrator, …) ran a
declared adapter and produced artifacts whose bytes we can re-hash. Nothing in
this repository can produce that today: the repo only holds static UXP package
structure checks. So this verifier's job is deliberately asymmetric:

* a **fake** E3 (a record that says ``level: "E3"`` with no ``host`` provenance,
  or with artifact hashes that do not match the files on disk) must fail here;
* **no record at all** must read as ``NO_RECORD`` — neither E3 nor a failure —
  and must never be silently rounded up to a capability level;
* this tool **never** writes, synthesises or promotes an E3 record. It only
  reads. Promoting a level stays a human/owner decision bound to a real host run.

Checks performed per record (all fail-closed):

1. contract: the record validates against
   ``design-lab/schemas/evidence-record.schema.json`` (draft 2020-12), which
   requires the ``host`` provenance block whenever ``level == "E3"``. The
   repository's ``jsonschema`` is used when importable; otherwise an equivalent
   built-in subset validator runs, so the gate still works in a bare stdlib
   environment (force it with ``DL_HOST_E3_FORCE_FALLBACK=1``).
2. ``level`` is exactly ``E3`` — any other level in the host-e3 store is reported
   INVALID because it is not host E3 evidence.
3. ``approver`` is non-empty (an E3 without a named approver is unsigned).
4. ``boundTreeSha`` is HEAD or a proper ancestor of HEAD (``git merge-base
   --is-ancestor``). A sibling/descendant/unrelated SHA is INVALID.
5. every ``host.artifacts[i].sha256`` equals the real SHA-256 of the file at
   ``host.artifacts[i].path`` (relative paths resolve against the repository
   root first, then against the record's own directory).

Usage:
    python design-lab/scripts/verify_host_e3_evidence.py [--record PATH]... [--dir DIR]

Output contract (one line, machine-parsed):
    HOST_E3=<NO_RECORD|VALID|INVALID> records=N findings=[...]

Exit code: 0 for NO_RECORD and VALID, 1 for INVALID.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "design-lab" / "schemas" / "evidence-record.schema.json"
# Runtime evidence lives under the ignored runtime root (never tracked).
DEFAULT_DIR_NAME = Path(".project-local") / "task-artifacts" / "host-e3"
FALLBACK_ENV = "DL_HOST_E3_FORCE_FALLBACK"

NO_RECORD_NOTE = "当前没有 host E3 证据，能力等级不得因此提升"
NO_RECORD_DETAIL = ("没有记录既不是 E3、也不是失败；本工具绝不生成、推断或提升任何能力等级，"
                    "E3 只能由真实宿主运行 + 人工授权产生。")
INVALID_DETAIL = "存在 host E3 声称但校验未通过；能力等级不得提升，本工具绝不生成或提升 E3。"
VALID_DETAIL = "记录通过契约、产物哈希、bound tree 与 approver 校验；是否据此提升等级仍由人工门决定。"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


# --------------------------------------------------------------------------- #
# contract validation
# --------------------------------------------------------------------------- #
def load_schema(path: Path = SCHEMA_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _type_ok(value, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def fallback_errors(instance, schema: dict, path: str = "$") -> list[str]:
    """Equivalent subset validator for the features this schema actually uses.

    Supported: type, const, enum, minLength, pattern, minItems, items, required,
    properties, additionalProperties:false, allOf and if/then. Unknown keywords
    are ignored (the schema is fixed and reviewed in-tree; it is not
    attacker-supplied).
    """
    errors: list[str] = []
    if not isinstance(schema, dict):
        return errors
    for sub in schema.get("allOf", []):
        errors.extend(fallback_errors(instance, sub, path))
    if "if" in schema:
        condition_matched = not fallback_errors(instance, schema["if"], path)
        if condition_matched and "then" in schema:
            errors.extend(fallback_errors(instance, schema["then"], path))
    expected = schema.get("type")
    if expected is not None:
        types = expected if isinstance(expected, list) else [expected]
        if not any(_type_ok(instance, t) for t in types):
            errors.append(f"{path}: {instance!r} is not of type {expected!r}")
            return errors
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: {instance!r} is not the constant {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']!r}")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: {instance!r} is shorter than minLength {schema['minLength']}")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(f"{path}: {instance!r} does not match pattern {schema['pattern']!r}")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems {schema['minItems']} items")
        if "items" in schema:
            for index, item in enumerate(instance):
                errors.extend(fallback_errors(item, schema["items"], f"{path}[{index}]"))
    if isinstance(instance, dict):
        for name in schema.get("required", []):
            if name not in instance:
                errors.append(f"{path}: '{name}' is a required property")
        properties = schema.get("properties", {})
        for name, sub in properties.items():
            if name in instance:
                errors.extend(fallback_errors(instance[name], sub, f"{path}.{name}"))
        if schema.get("additionalProperties") is False:
            for name in instance:
                if name not in properties:
                    errors.append(f"{path}: additional property '{name}' is not allowed")
    return errors


def contract_errors(record, schema: dict | None = None) -> tuple[list[str], str]:
    """(errors, engine). jsonschema when importable, else the built-in validator."""
    schema = load_schema() if schema is None else schema
    force_fallback = os.environ.get(FALLBACK_ENV, "").strip() not in ("", "0", "false")
    if not force_fallback:
        try:
            import jsonschema  # noqa: PLC0415 — optional, existing repo dependency
        except ImportError:
            jsonschema = None
        if jsonschema is not None:
            validator = jsonschema.Draft202012Validator(schema)
            errors = [f"{'/'.join(str(p) for p in error.absolute_path) or '$'}: {error.message}"
                      for error in validator.iter_errors(record)]
            return errors, "jsonschema"
    return fallback_errors(record, schema), "builtin"


# --------------------------------------------------------------------------- #
# hashing / git
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def head_sha(repo: Path = REPO) -> str:
    result = git(repo, "rev-parse", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else ""


def is_head_or_ancestor(sha: str, head: str, repo: Path = REPO) -> bool:
    """True only for HEAD itself or a commit HEAD descends from.

    ``git merge-base --is-ancestor <sha> HEAD`` exits 0 exactly in that case, so
    a sibling branch tip, an unrelated SHA or a descendant is rejected.
    """
    if not sha or not head:
        return False
    if sha == head:
        return True
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", sha):
        return False
    return git(repo, "merge-base", "--is-ancestor", sha, head).returncode == 0


def resolve_artifact(raw: str, record_path: Path, repo: Path) -> Path:
    """Absolute paths as-is; relative ones against the repo root, then the record dir."""
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    for base in (repo, record_path.parent):
        if (base / candidate).is_file():
            return base / candidate
    return repo / candidate


# --------------------------------------------------------------------------- #
# per-record evaluation
# --------------------------------------------------------------------------- #
def evaluate_record(path: Path, head: str, repo: Path = REPO) -> list[str]:
    """findings for one candidate record; empty list means this record is valid E3."""
    findings: list[str] = []
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{path}: unreadable record ({exc})"]
    if not isinstance(record, dict):
        return [f"{path}: record is not a JSON object"]

    errors, engine = contract_errors(record)
    findings.extend(f"{path}: schema ({engine}): {error}" for error in errors)

    if record.get("level") != "E3":
        findings.append(f"{path}: level={record.get('level')!r} is not 'E3' — "
                        f"该记录不是 host E3 证据，不得计入")
        return findings

    if not str(record.get("approver") or "").strip():
        findings.append(f"{path}: approver is empty — E3 需要具名的人工授权")

    bound = str(record.get("boundTreeSha") or "")
    if not head:
        findings.append(f"{path}: bound tree cannot be checked — git rev-parse HEAD returned nothing")
    elif not is_head_or_ancestor(bound, head, repo):
        findings.append(f"{path}: boundTreeSha={bound!r} is neither HEAD={head[:12]} "
                        f"nor one of its ancestors")

    host = record.get("host")
    if not isinstance(host, dict):
        findings.append(f"{path}: host provenance block is absent — "
                        f"没有宿主来源的 'E3' 是伪造的，不予通过")
        return findings

    declared_adapter = str(host.get("adapterSha256") or "")
    if not _SHA256_RE.match(declared_adapter):
        findings.append(f"{path}: host.adapterSha256={declared_adapter!r} is not a sha256 hex digest")

    artifacts = host.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        findings.append(f"{path}: host.artifacts is empty — 没有可校验的产物哈希，"
                        f"该 'E3' 不可验证")
        return findings
    for index, item in enumerate(artifacts):
        if not isinstance(item, dict):
            findings.append(f"{path}: host.artifacts[{index}] is not an object")
            continue
        raw_path = str(item.get("path") or "")
        declared = str(item.get("sha256") or "").lower()
        target = resolve_artifact(raw_path, path, repo)
        if not target.is_file():
            findings.append(f"{path}: host.artifacts[{index}] file not found: {raw_path} "
                            f"(resolved to {target})")
            continue
        actual = sha256_file(target)
        if declared != actual:
            findings.append(f"{path}: host.artifacts[{index}] sha256 mismatch for {raw_path}: "
                            f"declared={declared or '<missing>'} actual={actual}")
    return findings


def collect_records(explicit: list[str], scan_dir: Path) -> list[Path]:
    """Explicit --record paths win; otherwise the convention dir's *.json files."""
    if explicit:
        return [Path(item) for item in explicit]
    if not scan_dir.is_dir():
        return []
    return sorted(scan_dir.glob("*.json"))


# --------------------------------------------------------------------------- #
# entrypoint
# --------------------------------------------------------------------------- #
def main(argv=None, repo: Path = REPO, scan_dir: Path | None = None, head: str | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--record", action="append", default=[], metavar="PATH",
                        help="explicit evidence record to verify (repeatable)")
    parser.add_argument("--dir", default=None, metavar="DIR",
                        help="scan this directory instead of the convention directory")
    args = parser.parse_args(argv)

    base_dir = Path(args.dir) if args.dir else (scan_dir or (repo / DEFAULT_DIR_NAME))
    records = collect_records(list(args.record), base_dir)
    resolved_head = head if head is not None else head_sha(repo)

    findings: list[str] = []
    if not records:
        verdict = "NO_RECORD"
    else:
        for path in records:
            if not path.is_file():
                findings.append(f"{path}: record file not found (--record 指向的文件不存在)")
                continue
            findings.extend(evaluate_record(path, resolved_head, repo))
        verdict = "VALID" if not findings else "INVALID"

    print(f"HOST_E3={verdict} records={len(records)} "
          f"findings={json.dumps(findings, ensure_ascii=False)}")
    if verdict == "NO_RECORD":
        print(NO_RECORD_NOTE)
        print(f"HOST_E3_DETAIL={NO_RECORD_DETAIL}")
        return 0
    if verdict == "INVALID":
        for finding in findings:
            print(f"  FINDING {finding}")
        print(f"HOST_E3_DETAIL={INVALID_DETAIL}")
        return 1
    print(f"HOST_E3_DETAIL={VALID_DETAIL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
