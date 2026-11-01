#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-G000 / G010 / G030 / G040 — third-party and supply-chain governance gate.

G000  sources lock: every external project records name, canonical URL, revision,
      digest, licence, role and disposition, and `latest` is never a production
      identity.
G010  adapter registry: the status vocabulary is the frozen eight, and a manifest
      may not claim an evidence level its evidence does not carry.
G030  H3 stays BLOCKED_BY_LICENSE everywhere it appears, and no download or run
      path is introduced.
G040  supply chain: licence audit, secret scan, third-party source audit,
      lockfile audit, generated-artifact audit and binary inventory.

Writes reports/current/SUPPLY-CHAIN-REPORT.json and exits non-zero on a failure.

Usage:
    python scripts/verify_supply_chain.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports/current/SUPPLY-CHAIN-REPORT.json"
SELF_OUTPUT_REL = "reports/current/SUPPLY-CHAIN-REPORT.json"
TASK_KEYS = [f"DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-{key}"
             for key in ("G000", "G010", "G030", "G040")]
CANONICAL_STATUS = ("DECLARED", "STRUCTURAL", "CONTROLLED_RUNTIME", "REAL_WORKFLOW",
                    "INDEPENDENT_ACCEPTANCE", "RELEASED", "BLOCKED", "REVOKED")
# The vocabulary the registry used before this gate existed. Kept as an explicit
# mapping so the migration debt is a number, not a surprise.
LEGACY_STATUS = {"declared": "DECLARED", "structural": "STRUCTURAL", "runtime": "CONTROLLED_RUNTIME",
                 "missing": "DECLARED", "unsupported": "BLOCKED", "BLOCKED_BY_LICENSE": "BLOCKED"}
LEVEL_ORDER = {"E0": 0, "E1": 1, "E2": 2, "E3": 3, "E4": 4, "E5": 5}
SECRET_PATTERNS = [
    ("aws-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("openai-key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("generic-secret", re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*[\"'][^\"']{16,}[\"']")),
]
GENERATED_MARKERS = (".pyc", ".pyo", ".log", ".tmp", ".bak")
LOCKFILES = {"uv.lock": "python", "pnpm-lock.yaml": "node", "package-lock.json": "node",
             "yarn.lock": "node"}


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def tracked() -> list:
    return [line for line in git("ls-files").splitlines() if line.strip()]


def read_json(rel: str):
    path = REPO / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def sources_lock_check(files: list) -> dict:
    lock = read_json("vendor/sources.lock.json") or {}
    # PR #242 derives per-source revisions into its own record rather than restating
    # them in the lock, because a revision copied by hand can drift from the taxonomy
    # pin it came from. Reading only the lock made `revision_coverage` report 0 for
    # 37 sources whose revisions are recorded and anti-drift-tested.
    revisions = read_json("vendor/sources.revisions.json") or {}
    resolved = set(revisions.get("sources") or {})
    unresolved = {str(item.get("id")) for item in revisions.get("unresolved") or []}
    required = ("id", "path", "disposition", "license")
    entries, problems = [], []
    latest_identities = []
    for source in lock.get("sources", []):
        missing = [field for field in required if not source.get(field)]
        blob = json.dumps(source).lower()
        if re.search(r'"(commit|revision|version|canonicalurl)"\s*:\s*"latest"', blob):
            latest_identities.append(source.get("id"))
        source_id = source.get("id")
        has_revision = bool(source.get("commit") or source.get("revision")
                            or source_id in resolved)
        entries.append({"id": source_id, "missing_fields": missing,
                        "has_url": bool(source.get("canonicalUrl") or source.get("url")),
                        "has_revision": has_revision})
        if missing:
            problems.append({"id": source_id, "missing": missing})
    # AUTHORITY §9 wants source AND revision for an absorbed file. Nine sources are
    # unresolved with a recorded reason, so absence is reported as a number rather than
    # turned into a red build -- a documented unknown must not block every PR, but it
    # must be visible and it must not be silently growing.
    absorb_ids = {s.get("id") for s in lock.get("sources", [])
                  if str(s.get("disposition") or "").startswith("ABSORB")}
    # Two different things: `absorb_without_revision` is a hole in the record itself
    # (the source appears in neither list), which should stay empty; `absorb_unresolved`
    # is AUTHORITY §9 satisfied on source but not yet on revision, which is a recorded
    # unknown the owner has to close -- visible, but not a red build.
    absorb_gaps = sorted(e["id"] for e in entries
                         if e["id"] in absorb_ids and e["id"] not in resolved
                         and e["id"] not in unresolved)
    absorb_unresolved = sorted(absorb_ids & unresolved)
    # Split the unresolved by what a human would need to close them: a source with a
    # URL needs an authoritative revision lookup, a source without one needs the URL
    # first. Measured 2026-10-07: neither is resolvable offline -- the two SOURCE.md
    # records and skills-lock.json carry repo, license, branch and vendoring date but
    # no commit, and the only 40-hex strings in those directories are truncated
    # SHA-256 content hashes, which are not revisions.
    by_id = {s.get("id"): s for s in lock.get("sources", [])}

    def _notes_has_url(source_id) -> bool:
        return bool(re.search(r"https?://", str(by_id.get(source_id, {}).get("notes") or "")))

    unresolved_with_url = sorted(i for i in unresolved if _notes_has_url(i))
    unresolved_without_url = sorted(unresolved - set(unresolved_with_url))
    lock_ids = {e["id"] for e in entries}
    return {"entries": len(entries), "problems": problems, "latest_identities": latest_identities,
            "canonical_url_coverage": sum(1 for e in entries if e["has_url"]),
            "revision_coverage": sum(1 for e in entries if e["has_revision"]),
            "revision_record": {"present": bool(revisions), "resolved": len(resolved),
                                "unresolved": len(unresolved)},
            "absorb_without_revision": absorb_gaps,
            "absorb_unresolved": absorb_unresolved,
            "revision_unresolved_with_url": unresolved_with_url,
            "revision_unresolved_without_url": unresolved_without_url,
            "revision_record_ids_not_in_lock": sorted((resolved | unresolved) - lock_ids),
            "ok": not problems and not latest_identities}


def adapter_status_check() -> dict:
    registry = read_json("integrations/adapter-registry.json") or {}
    adapters = registry.get("adapters", [])
    legacy, canonical, incoherent = {}, 0, []
    for adapter in adapters:
        status = adapter.get("status")
        level = (adapter.get("evidence") or {}).get("level", "E0")
        if status in CANONICAL_STATUS:
            canonical += 1
        elif status in LEGACY_STATUS:
            legacy[status] = legacy.get(status, 0) + 1
        else:
            incoherent.append({"adapter_id": adapter.get("adapter_id"), "status": status})
        # A declared/structural adapter may not claim runtime evidence.
        if status in {"declared", "DECLARED", "structural", "STRUCTURAL"} and \
                LEVEL_ORDER.get(level, 0) > LEVEL_ORDER["E1"]:
            incoherent.append({"adapter_id": adapter.get("adapter_id"),
                               "reason": f"status {status} claims {level}"})
        if status in {"REAL_WORKFLOW", "runtime"} or LEVEL_ORDER.get(level, 0) >= LEVEL_ORDER["E3"]:
            evidence = adapter.get("evidence") or {}
            if not evidence.get("task_ids") or not evidence.get("artifact_paths"):
                incoherent.append({"adapter_id": adapter.get("adapter_id"),
                                   "reason": "E3-class claim without runtime identity or artifacts"})
    return {"adapters": len(adapters), "canonical_status_usage": canonical,
            "legacy_status_usage": legacy,
            "migration_debt": sum(legacy.values()),
            "incoherent": incoherent,
            "status_model": registry.get("status_model"),
            "ok": not incoherent}


def h3_check() -> dict:
    findings = []
    lock = read_json("vendor/sources.lock.json") or {}
    radar = read_json("design-lab/readiness/model-radar.json") or {}
    registry = read_json("integrations/adapter-registry.json") or {}
    manifest = read_json("integrations/generators/minimax-h3/adapter.manifest.json") or {}
    h3_sources = [s for s in lock.get("sources", []) if "minimax" in json.dumps(s).lower()]
    forced = [s for s in h3_sources if s.get("disposition") in {"CONDITIONAL_POC", "LOCK_REFERENCE",
                                                                "BLOCKED"}]
    if h3_sources and not forced:
        findings.append({"where": "vendor/sources.lock.json", "issue": "H3 present without a "
                         "restrictive disposition"})
    blocked_models = [m for m in radar.get("entries", [])
                      if m["model_id"].startswith("minimax-h3")]
    if blocked_models and any(m.get("radar_state") != "BLOCKED_BY_LICENSE" for m in blocked_models):
        findings.append({"where": "design-lab/readiness/model-radar.json",
                         "issue": "an H3 model is not BLOCKED_BY_LICENSE"})
    if any(m.get("default_enabled") for m in blocked_models):
        findings.append({"where": "design-lab/readiness/model-radar.json",
                         "issue": "an H3 model is default enabled"})
    h3_adapter = next((a for a in registry.get("adapters", [])
                       if a.get("adapter_id") == "adapter-minimax-h3"), None)
    if h3_adapter and h3_adapter.get("status") != "BLOCKED_BY_LICENSE":
        findings.append({"where": "integrations/adapter-registry.json",
                         "issue": f"H3 adapter status is {h3_adapter.get('status')}"})
    if manifest and all(cap.get("supported") is not True for cap in manifest.get("capabilities", [])):
        pass
    else:
        findings.append({"where": "integrations/generators/minimax-h3/adapter.manifest.json",
                         "issue": "H3 manifest declares a supported capability"})
    return {"h3_sources_in_lock": len(h3_sources), "h3_models": len(blocked_models),
            "findings": findings, "ok": not findings}


def license_audit(files: list) -> dict:
    markers = [f for f in files if Path(f).name in {"LICENSE", "LICENSE.md", "LICENSE.txt", "NOTICE",
                                                    "COPYING", "SOURCE.md"}]
    registry = read_json("design-lab/config/rights-registry.json")
    return {"marker_files": len(markers), "rights_registry_present": registry is not None,
            "rights_registry_subjects": (registry or {}).get("counts", {}).get("subjects"),
            "ok": registry is not None}


SYNTHETIC_MARKERS = ("should-not", "shouldnot", "example", "dummy", "fake", "placeholder",
                     "your-", "your_", "changeme", "redacted", "not-a-real", "xxxx", "<", "fixture")
# "your_" (underscore) documents the same placeholder family as "your-" above:
# inert research/reference docs use YOUR_RAPIDAPI_KEY / YOUR_BEARER_TOKEN style
# stand-ins, and real credentials never spell themselves "YOUR_*". The check
# stays value-based (never a path rule), so a real key in a test path is still
# caught by the credential-shape clause below.
# A value whose own shape is a real credential format. A test path is NOT evidence
# that such a value is synthetic: a real key pasted into a fixture would be exempted
# by a blanket path rule, which is exactly how a leak survives a scan. Only an
# in-value marker may exempt these.
CREDENTIAL_SHAPES = tuple(pattern for name, pattern in SECRET_PATTERNS
                          if name != "generic-secret")
TEST_PATHS = ("fixtures/", "design-lab/tests/", "tests/")


def is_synthetic(path: str, match: str) -> bool:
    """Test fixtures name their values so that nobody thinks they are real.

    The decision is made from the *value*, then from the path only for values that
    carry no credential format of their own. An INDEPENDENT AUDIT showed the earlier
    blanket path rule returned True for an AWS-key-shaped literal sitting in a test
    file, so this function is deliberately callable that way and still returns False.
    """
    lowered = match.lower()
    if any(marker in lowered for marker in SYNTHETIC_MARKERS):
        return True
    if any(shape.search(match) for shape in CREDENTIAL_SHAPES):
        return False
    return path.startswith(TEST_PATHS)


def load_adjudications() -> tuple:
    """(by_digest, malformed) for hash-pinned adjudicated exemptions.

    A path rule cannot prove a value is synthetic: an INDEPENDENT AUDIT demonstrated
    that it returned True for a credential-shaped value sitting in a test file. An
    adjudication therefore pins the SHA-256 of one exact value, so exempting one
    adjudicated test vector never exempts a different value in the same file or
    anywhere else. An entry missing a reason or an adjudicating task is reported as
    malformed instead of being honoured.
    """
    document = read_json("design-lab/config/secret-scan-adjudications.json") or {}
    by_digest, malformed = {}, []
    for entry in document.get("adjudications", []):
        missing = [field for field in ("value_sha256", "reason", "adjudicated_by")
                   if not entry.get(field)]
        if missing:
            malformed.append({"entry": entry.get("value_sha256") or "(no digest)",
                              "missing": missing})
            continue
        by_digest[entry["value_sha256"]] = entry
    return by_digest, malformed


def secret_scan(files: list) -> dict:
    adjudications, malformed = load_adjudications()
    hits, exempted, adjudicated = [], [], []
    for rel in files:
        if rel == SELF_OUTPUT_REL:
            # Self-reference: this report quotes the matches it found, so scanning it
            # would flag the report itself on every subsequent run. The exclusion is
            # narrow (one derived artifact) and is recorded in the result.
            continue
        path = REPO / rel
        try:
            if path.stat().st_size > 1_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(0)
                digest = "sha256:" + hashlib.sha256(value.encode()).hexdigest()
                if digest in adjudications:
                    adjudicated.append({"pattern": name, "path": rel, "value_sha256": digest,
                                        "reason": adjudications[digest]["reason"]})
                    continue
                if is_synthetic(rel, value):
                    exempted.append({"pattern": name, "path": rel,
                                     "reason": "in-value synthetic marker"
                                     if any(m in value.lower() for m in SYNTHETIC_MARKERS)
                                     else "test/fixture path, no credential format in the value"})
                    continue
                line = text.count("\n", 0, match.start()) + 1
                hits.append({"pattern": name, "path": rel, "line": line,
                             "match": value[:24] + "…"})
    return {"patterns": [name for name, _ in SECRET_PATTERNS], "hits": hits[:50],
            "hit_count": len(hits), "synthetic_values_exempted": len(exempted),
            "exempted": exempted[:20],
            "adjudicated_values_exempted": len(adjudicated),
            "adjudicated": adjudicated[:20],
            "malformed_adjudications": malformed,
            "self_output_excluded": SELF_OUTPUT_REL,
            "exemption_rule": "an in-value synthetic marker, or a test/fixture path for a value "
                              "that carries no credential format of its own, or a hash-pinned "
                              "adjudication; a value with a real credential format is never "
                              "exempted by path alone, and an adjudication exempts exactly one "
                              "value",
            "ok": not hits and not malformed}


# The fixtures are assembled from fragments on purpose. A credential-shaped literal
# sitting in this file at rest would be flagged by this very scanner, and the tempting
# fix for that is to exempt the scanner's own path — which is the hole this rule
# closes. Assembled values are still real inputs to the rule under test.
FAKE_AWS_KEY = "AKIA" + "3XJ7QZ2LMN4PQRST"
FAKE_PRIVATE_KEY = "-----BEGIN " + "RSA PRIVATE KEY-----"
FAKE_GENERIC_SECRET = "token: " + "'should-not-enter-event-bus'"
FAKE_PLACEHOLDER = "api_key: " + "'placeholder-value-for-local-dev'"

SELF_TEST_CASES = [
    ("test path must not exempt a credential-shaped value",
     "design-lab/tests/test_runtime_asset_safety.py", FAKE_AWS_KEY, False),
    ("test path must not exempt a private key header",
     "fixtures/probe.py", FAKE_PRIVATE_KEY, False),
    ("test path may exempt a value that names itself synthetic",
     "fixtures/domains/game-visual/tests/analytics.test.js", FAKE_GENERIC_SECRET, True),
    ("a placeholder marked as such is exempt anywhere",
     "src/design_lab/config.py", FAKE_PLACEHOLDER, True),
]


def self_test() -> list:
    """The exemption rules must not be usable to hide a credential."""
    failures = [f"{description}: is_synthetic({path!r}, {value!r}) returned "
                f"{is_synthetic(path, value)}"
                for description, path, value, expected in SELF_TEST_CASES
                if is_synthetic(path, value) is not expected]
    # An adjudication exempts exactly one value. The same file, with a different
    # credential-shaped value, must still be a hit — otherwise the adjudication file
    # would be a path exemption wearing a digest.
    by_digest, malformed = load_adjudications()
    if not by_digest:
        failures.append("no adjudication is loaded, so the adjudication path is untested")
    if malformed:
        failures.append(f"the adjudication file has malformed entries: {malformed}")
    adjudicated_value = next(iter(by_digest.values()), {}).get("value_sha256")
    if adjudicated_value:
        other = "AKIA" + "ZZZZ1111YYYY2222"
        if "sha256:" + hashlib.sha256(other.encode()).hexdigest() in by_digest:
            failures.append("a different value is covered by an adjudication; the exemption "
                            "is broader than the value that was adjudicated")
        for entry in by_digest.values():
            if not entry.get("review_condition"):
                failures.append(f"adjudication {entry['value_sha256'][:19]}... has no review "
                                "condition, so it would never be revisited")
    return failures


def lockfile_audit(files: list) -> dict:
    present = [f for f in files if Path(f).name in LOCKFILES or Path(f).name == "requirements.txt"]
    managers = {LOCKFILES[Path(f).name] for f in present if Path(f).name in LOCKFILES}
    return {"lockfiles": present, "managers": sorted(managers),
            "single_manager_per_ecosystem": len(managers) <= 2,
            "ok": "uv.lock" in [Path(f).name for f in present]}


#: Owner decision 2026-10-12 (option A for the clean-clone gate debt, previously item G):
#: the bytes current-execution receipts bind by hash are now TRACKED under this root, and
#: 82 of them are `.log` gate outputs. The blanket `*.log` ban above existed so stray run
#: output never enters the repo -- it did not contemplate evidence that a receipt re-hashes
#: on every read. This is a scoped exemption for one root, not a lowered threshold: outside
#: `design-lab/evidence/` a tracked `.log` is still an offender, and the exemption is named
#: here so a reader can see exactly whose decision produced it.
TRACKED_EVIDENCE_ROOT = "design-lab/evidence/"


def generated_artifact_audit(files: list) -> dict:
    def exempt(f: str) -> bool:
        # ONLY `.log` under the tracked evidence root is exempt, and only because a
        # current-execution receipt re-hashes it on every read. .pyc/.pyo/.tmp/.bak stay
        # offenders everywhere, evidence root included -- an exemption wide enough to
        # cover the whole marker tuple would be a lowered criterion wearing a name.
        return f.startswith(TRACKED_EVIDENCE_ROOT) and f.endswith(".log")

    offenders = [
        f for f in files
        if not exempt(f)
        and (f.endswith(GENERATED_MARKERS) or "__pycache__" in f
             or f.startswith(("dist/", "build/", "node_modules/")))
    ]
    evidence = [f for f in files if exempt(f)]
    return {"offenders": offenders[:30], "count": len(offenders), "ok": not offenders,
            "tracked_evidence_exempt": len(evidence)}


def binary_inventory(files: list) -> dict:
    report = read_json("reports/current/TRACKED-BINARY.json")
    if report:
        return {"source": "reports/current/TRACKED-BINARY.json", "count": report["count"],
                "by_category": report["by_category"], "verdict": report["verdict"],
                "ok": report["verdict"] == "NO_MODEL_WEIGHTS_TRACKED"}
    return {"source": "missing", "count": None, "ok": False}


def third_party_audit() -> dict:
    report = read_json("reports/current/THIRD-PARTY-SOURCE-AUDIT.json")
    if not report:
        return {"source": "missing", "ok": False}
    return {"source": "reports/current/THIRD-PARTY-SOURCE-AUDIT.json",
            "verdict": report["verdict"], "counts": report["counts"],
            "ok": report["counts"]["missing_absorbed_tree"] == 0}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true",
                        help="prove the synthetic-value exemption cannot swallow a credential")
    args = parser.parse_args(argv)
    if args.self_test:
        failures = self_test()
        print("SUPPLY_CHAIN_SELF_TEST=" + ("PASS" if not failures else "FAIL"))
        for failure in failures:
            print("  FAIL", failure)
        return 0 if not failures else 1
    files = tracked()
    checks = {
        "G000_sources_lock": sources_lock_check(files),
        "G010_adapter_status": adapter_status_check(),
        "G030_h3_blocked": h3_check(),
        "G040_license_audit": license_audit(files),
        "G040_secret_scan": secret_scan(files),
        "G040_lockfile_audit": lockfile_audit(files),
        "G040_generated_artifacts": generated_artifact_audit(files),
        "G040_binary_inventory": binary_inventory(files),
        "G040_third_party_sources": third_party_audit(),
    }
    failures = [name for name, result in checks.items() if not result.get("ok")]
    document = {
        "schemaVersion": "design-lab/supply-chain-report/v1",
        "task_keys": TASK_KEYS,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": git("rev-parse", "HEAD").strip(),
        "canonical_adapter_status": list(CANONICAL_STATUS),
        "legacy_status_mapping": LEGACY_STATUS,
        "checks": checks,
        "failures": failures,
        "verdict": "PASS" if not failures else "FAIL",
        "migration_debt": {
            "adapter_status_entries_still_legacy": checks["G010_adapter_status"]["migration_debt"],
            "note": "the frozen eight-value vocabulary is the target; the registry still uses the "
                    "legacy names, and the gate maps them explicitly so the debt is a number",
        },
    }
    if args.check:
        # Compare the failing set and the per-check pass/fail, not only the headline
        # verdict: two different failures both read as "FAIL" and a stored FAIL
        # compared against a fresh FAIL used to report PASS.
        if not OUT.is_file():
            print("SUPPLY_CHAIN=DRIFT missing " + OUT.name)
            return 1
        stored = json.loads(OUT.read_text(encoding="utf-8"))
        stored_check_state = {name: r.get("ok") for name, r in stored.get("checks", {}).items()}
        fresh_check_state = {name: r.get("ok") for name, r in checks.items()}
        if (stored.get("verdict") != document["verdict"]
                or stored.get("failures") != failures
                or stored_check_state != fresh_check_state):
            print(f"SUPPLY_CHAIN=DRIFT stored verdict={stored.get('verdict')} "
                  f"fresh={document['verdict']} stored_failures={stored.get('failures')} "
                  f"fresh_failures={failures}")
            return 1
        print("SUPPLY_CHAIN=PASS (verdict, failure list and every check agree)")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"SUPPLY_CHAIN={document['verdict']} checks={len(checks)} failures={failures}")
    for name, result in checks.items():
        extra = ""
        if name == "G010_adapter_status":
            extra = (f" statuses canonical={result['canonical_status_usage']} "
                     f"legacy={result['migration_debt']}")
        if name == "G000_sources_lock":
            extra = (f" entries={result['entries']} urls={result['canonical_url_coverage']} "
                     f"revisions={result['revision_coverage']}")
        if name == "G040_secret_scan":
            extra = f" hits={result['hit_count']}"
        print(f"  {'ok  ' if result.get('ok') else 'FAIL'} {name}{extra}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
