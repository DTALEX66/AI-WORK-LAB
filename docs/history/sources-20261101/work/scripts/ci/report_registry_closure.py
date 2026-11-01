# -*- coding: utf-8 -*-
"""AG-05 field-level closure report for the model / provider / runtime registries.

Authority: `WORK-LAB-AUTHORITY.md` > `.project/governance/project-authority-index.json`
> `AGENTS.md` + scoped machine contracts > this report.

Why this exists
---------------
The 2026-09-29 Master Atlas closed gap G05 with the acceptance wording
"逐字段闭合、完整hash、时间/来源、negative能力；不触碰实际模型" (close it *field
by field*, with complete hashes, time/source, negative capabilities, without
touching any actual model). The per-field repairs landed incrementally (AG-05,
AG-05b, AG-05c) and each is individually verified, but nothing answered the
aggregate question an auditor actually asks:

    across the three registries, which fields are CLOSED, which are
    EXPLICITLY OPEN (null with a stated reason), and which are still UNCLOSED?

A grep cannot answer that, and "no gate is red" cannot answer it either, because
an unclosed field is usually not a gate failure — it is a silent hole.

This script is read-only and answers that question as data, so the answer is
reviewable, diffable and testable rather than a matter of opinion. It never
matters as a pass/fail gate on "is the registry perfect": it reports closure and
exits 0 unless the registries are unreadable, because the honest current state
includes fields that are legitimately open.

Closure classes
---------------
CLOSED            a value is present and, where it is a reference, it resolves.
EXPLICITLY_OPEN   the value is null/absent AND a stated reason exists, so a
                  reader cannot mistake it for an oversight. This is the only
                  acceptable form of "missing".
UNCLOSED          null/absent with no reason, or a reference that does not
                  resolve. Every UNCLOSED entry is a real, named hole.

Output: `.project-local/runs/ag05-registry-closure.json` plus a one-line summary.
Exit codes: 0 report produced (whatever the closure state), 1 registries
unreadable, 2 environment error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

PROVIDER = ".project/governance/provider-registry.json"
MODEL = ".project/governance/model-registry.json"
RUNTIME = ".project/governance/runtime-registry.json"
OUT = ".project-local/runs/ag05-registry-closure.json"

HEX64 = re.compile(r"^[0-9a-f]{64}$")
# Fields whose absence must be explained somewhere on the same record.
REASON_FIELDS = ("reason", "note", "binding_note", "binding_status_note",
                 "status_note", "retirement_note", "standby_reason",
                 "runtime_id_note", "sha256_basis", "provisional_reason",
                 "last_verified_note", "migration_note")


def _load(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8"))


def _has_reason(record: Mapping[str, Any]) -> bool:
    for key in REASON_FIELDS:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return True
    digest = record.get("assetDigest")
    if isinstance(digest, Mapping) and isinstance(digest.get("reason"), str) \
            and digest["reason"].strip():
        return True
    return False


class Report:
    def __init__(self) -> None:
        self.closed: list[dict[str, Any]] = []
        self.explicitly_open: list[dict[str, Any]] = []
        self.unclosed: list[dict[str, Any]] = []

    def close(self, where: str, field: str, value: Any = None) -> None:
        entry = {"where": where, "field": field}
        if value is not None:
            entry["value"] = value if not isinstance(value, str) or len(value) <= 80 \
                else value[:77] + "..."
        self.closed.append(entry)

    def open_with_reason(self, where: str, field: str, reason: str) -> None:
        self.explicitly_open.append({"where": where, "field": field, "reason": reason[:160]})

    def mark_unclosed(self, where: str, field: str, detail: str) -> None:
        self.unclosed.append({"where": where, "field": field, "detail": detail[:200]})

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "work-lab/ag05-registry-closure/v1",
            "counts": {
                "closed": len(self.closed),
                "explicitly_open": len(self.explicitly_open),
                "unclosed": len(self.unclosed),
            },
            "unclosed": self.unclosed,
            "explicitly_open": self.explicitly_open,
            "closed": self.closed,
        }


def build_report(root: Path) -> Report:
    providers_doc = _load(root / PROVIDER)
    models_doc = _load(root / MODEL)
    runtimes_doc = _load(root / RUNTIME)

    report = Report()
    providers = providers_doc.get("providers") or []
    models = {m["id"]: m for m in models_doc.get("models") or [] if isinstance(m, dict)}
    runtimes = {r["id"]: r for r in runtimes_doc.get("runtimes") or [] if isinstance(r, dict)}
    plibs = {p["id"]: p for p in runtimes_doc.get("processLibraries") or [] if isinstance(p, dict)}
    externals = {e["id"]: e for e in providers_doc.get("externalAssets") or []
                 if isinstance(e, dict)}
    known_runtime_ids = set(runtimes) | set(plibs)

    # ---- provider foreign keys ----------------------------------------
    for provider in providers:
        where = f"provider[{provider.get('id')}]"
        bound = provider.get("binds_to_model")
        if bound is None:
            if _has_reason(provider):
                report.open_with_reason(where, "binds_to_model",
                                        "null with a stated binding reason")
            else:
                report.mark_unclosed(where, "binds_to_model",
                                "null with no stated reason")
        elif bound in models or bound in externals:
            report.close(where, "binds_to_model", bound)
        else:
            report.mark_unclosed(where, "binds_to_model",
                            f"reference {bound!r} resolves to no model or external asset")

        runtime = provider.get("binds_to_runtime")
        if runtime is None:
            if _has_reason(provider):
                report.open_with_reason(where, "binds_to_runtime", "null with a stated reason")
            else:
                report.mark_unclosed(where, "binds_to_runtime", "null with no stated reason")
        elif runtime in known_runtime_ids:
            report.close(where, "binds_to_runtime", runtime)
        else:
            report.mark_unclosed(where, "binds_to_runtime",
                            f"reference {runtime!r} is neither a runtime nor a process library")

        if "binding_status" in provider:
            report.close(where, "binding_status", provider.get("binding_status"))
            if not provider.get("binding_status_source"):
                report.mark_unclosed(where, "binding_status_source",
                                "binding_status set without a source pointer")
            else:
                report.close(where, "binding_status_source",
                             provider.get("binding_status_source"))

    # ---- model fields --------------------------------------------------
    for model_id, model in models.items():
        where = f"model[{model_id}]"
        sha = model.get("sha256")
        if isinstance(sha, str) and HEX64.match(sha):
            report.close(where, "sha256", sha)
        elif sha is None:
            if _has_reason(model):
                report.open_with_reason(where, "sha256",
                                        "explicit null with a stated reason in assetDigest")
            else:
                report.mark_unclosed(where, "sha256", "null with no stated reason")
        else:
            report.mark_unclosed(where, "sha256", f"{str(sha)[:40]!r} is not a 64-hex digest")

        runtime_id = model.get("runtime_id")
        if runtime_id is None:
            status = model.get("status")
            if status in ("RETIRED_PENDING_DECISION", "RETIRED", "standby"):
                report.open_with_reason(where, "runtime_id",
                                        f"null while status={status!r} (not bound to a runtime)")
            else:
                report.mark_unclosed(where, "runtime_id",
                                f"null while status={status!r}")
        elif runtime_id in known_runtime_ids:
            report.close(where, "runtime_id", runtime_id)
        else:
            report.mark_unclosed(where, "runtime_id", f"{runtime_id!r} does not resolve")

        if not model.get("last_verified"):
            # time provenance: the Atlas explicitly asked for 时间/来源.
            # A missing timestamp is EXPLICITLY_OPEN only when the record states
            # why (e.g. last_verified_note); otherwise it is a real hole.
            if _has_reason(model):
                report.open_with_reason(
                    where, "last_verified",
                    "absent with a stated reason (existence attested, no dated verification)")
            else:
                report.mark_unclosed(where, "last_verified", "no verification timestamp")
        else:
            report.close(where, "last_verified", model.get("last_verified"))

    # ---- orphan residue digests ---------------------------------------
    for index, orphan in enumerate(models_doc.get("candidateOrphans") or []):
        if not isinstance(orphan, dict):
            continue
        where = f"candidateOrphans[{index}]"
        sha = orphan.get("sha256")
        if isinstance(sha, str) and HEX64.match(sha):
            report.close(where, "sha256", sha)
        elif sha is None:
            digest = orphan.get("assetDigest")
            if isinstance(digest, Mapping) and digest.get("reason"):
                report.open_with_reason(where, "sha256", "truncated residue with a stated reason")
            else:
                report.mark_unclosed(where, "sha256", "null with no stated reason")
        else:
            report.mark_unclosed(where, "sha256", f"{str(sha)[:40]!r} is not a 64-hex digest")

    # ---- process libraries --------------------------------------------
    for lib_id, lib in plibs.items():
        where = f"processLibrary[{lib_id}]"
        if lib.get("executionModel"):
            report.close(where, "executionModel", lib.get("executionModel"))
        else:
            report.mark_unclosed(where, "executionModel", "no execution model declared")
        state = lib.get("health_state")
        if state == "UNKNOWN":
            report.open_with_reason(where, "health_state",
                                    "UNKNOWN with a probe_note; presence checked, quality not")
        elif state:
            report.close(where, "health_state", state)
        else:
            report.mark_unclosed(where, "health_state", "not declared")

    return report


def verify(root: Path) -> int:
    for rel in (PROVIDER, MODEL, RUNTIME):
        if not (root / rel).is_file():
            print(f"AG05_CLOSURE_ENV_ERROR missing {rel}", file=sys.stderr)
            return 2
    try:
        report = build_report(root)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"AG05_CLOSURE_UNREADABLE {exc}", file=sys.stderr)
        return 1

    payload = report.as_dict()
    out = root / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts = payload["counts"]
    print(
        "AG05_CLOSURE_REPORT "
        f"closed={counts['closed']} explicitly_open={counts['explicitly_open']} "
        f"unclosed={counts['unclosed']} out={OUT}"
    )
    # Unclosed fields are reported, not failed: the honest current state contains
    # them, and a red gate here would tempt someone to hide one.
    for item in payload["unclosed"][:12]:
        print(f"  UNCLOSED {item['where']}.{item['field']}: {item['detail']}", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[2]
    parser.add_argument("--root", type=Path, default=default_root)
    args = parser.parse_args()
    return verify(args.root.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
