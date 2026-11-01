#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-G020 — generate the rights registry from recorded facts.

Every model, provider, plugin, code donor, font, asset and external API needs an
entry carrying licence, territory, use restriction, output restriction,
redistribution, evidence source, observation date and a refresh policy.

This generator does **not** adjudicate. Where the repository has a recorded
decision (MiniMax H3 is BLOCKED_BY_LICENSE by rights decision R0-006), that
decision is carried over. Where it has only a licence identifier, the judgment
fields say `NOT_ADJUDICATED` and name the decision owner, because inventing a
legal position is exactly what this project forbids.

Authoring sources are projected, never copied: provider-capabilities.json,
vendor/sources.lock.json, readiness/model-radar.json and the licence texts.

Writes design-lab/config/rights-registry.json.

Usage:
    python scripts/generate_rights_registry.py [--check]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "design-lab/config/rights-registry.json"
TASK_KEY = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-G020"
DECISION_OWNER = "DTALEX66"
H3_BLOCK = {
    "territory": {"limits": ["EU", "UK", "KR", "US"], "state": "ADJUDICATED"},
    "use_restriction": "PERSONAL_RESEARCH_NONCOMMERCIAL_ONLY",
    "output_restriction": "NO_THIRD_PARTY_DISTRIBUTION",
    "redistribution": "FORBIDDEN",
    "refresh_policy": "BLOCKED_PENDING_OWNER",
    "adjudicated_by": "rights decision R0-006 (recorded in integrations/adapter-registry.json)",
}


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def pending(kind: str, subject: str, license_id, evidence: str, observed: str) -> dict:
    """An entry whose judgment fields the project has not decided."""
    return {
        "subject_id": subject,
        "kind": kind,
        "license": license_id or "unverified",
        "territory": {"limits": [], "state": "NOT_ADJUDICATED"},
        "use_restriction": "NOT_ADJUDICATED",
        "output_restriction": "NOT_ADJUDICATED",
        "redistribution": "NOT_ADJUDICATED",
        "evidence_source": evidence,
        "observed_at": observed,
        "refresh_policy": "REVIEW_BEFORE_DELIVERY",
        "adjudicated_by": None,
        "decision_owner": DECISION_OWNER,
    }


def build() -> dict:
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = []

    providers = json.loads((REPO / "design-lab/config/provider-capabilities.json").read_text(encoding="utf-8"))
    for provider in providers.get("providers", []):
        entries.append(pending("provider", provider["provider_id"], provider.get("license"),
                               "design-lab/config/provider-capabilities.json", observed))

    lock = json.loads((REPO / "vendor/sources.lock.json").read_text(encoding="utf-8"))
    for source in lock.get("sources", []):
        entry = pending("code-donor", f"vendor:{source['id']}", source.get("license"),
                        "vendor/sources.lock.json", source.get("observedAt") or observed)
        entry["disposition"] = source.get("disposition")
        entry["canonical_url"] = source.get("canonicalUrl")
        entries.append(entry)

    if (REPO / "design-lab/readiness/model-radar.json").is_file():
        radar = json.loads((REPO / "design-lab/readiness/model-radar.json").read_text(encoding="utf-8"))
        for model in radar.get("entries", []):
            rights = model.get("rights") or {}
            entry = pending("model", f"model:{model['model_id']}", rights.get("license_id"),
                            "design-lab/readiness/model-radar.json", observed)
            if model["model_id"].startswith("minimax-h3") or model.get("radar_state") == "BLOCKED_BY_LICENSE":
                entry.update(H3_BLOCK)
            else:
                entry["territory"] = {"limits": list(rights.get("territory_limits") or []),
                                      "state": "NOT_ADJUDICATED"}
            entry["commercial_use_recorded"] = rights.get("commercial_use")
            entries.append(entry)

    for name in ("LICENSES/MIT.txt", "NOTICE", "THIRD_PARTY_SOURCES_V2.md",
                 "THIRD_PARTY_SOURCES_VISUAL_V21.md", "LICENSING_DECISION_REQUIRED.md"):
        if (REPO / name).is_file():
            entries.append(pending("license-text", f"repo:{name}", "see file", name, observed))

    return {
        "schemaVersion": "design-lab/rights-registry/v1",
        "task_key": TASK_KEY,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": git("rev-parse", "HEAD"),
        "field_meaning": {
            "NOT_ADJUDICATED": "the repository records no decision for this field; the decision "
                               "owner must supply one. The registry never guesses a legal position.",
            "adjudicated_by": "the recorded decision this entry carries, or null when none exists",
        },
        "decision_owner": DECISION_OWNER,
        "generated_from": ["design-lab/config/provider-capabilities.json", "vendor/sources.lock.json",
                           "design-lab/readiness/model-radar.json", "LICENSES/", "NOTICE"],
        "entries": entries,
        "counts": {
            "subjects": len(entries),
            "adjudicated": sum(1 for e in entries if e["adjudicated_by"]),
            "awaiting_adjudication": sum(1 for e in entries if not e["adjudicated_by"]),
            "blocked_pending_owner": sum(1 for e in entries
                                         if e["refresh_policy"] == "BLOCKED_PENDING_OWNER"),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    document = build()
    if args.check:
        if not OUT.is_file():
            print("RIGHTS_REGISTRY=FAIL missing")
            return 1
        current = json.loads(OUT.read_text(encoding="utf-8"))
        same = current["counts"] == document["counts"] and \
            [e["subject_id"] for e in current["entries"]] == [e["subject_id"] for e in document["entries"]]
        print("RIGHTS_REGISTRY=" + ("PASS" if same else "DRIFT"))
        return 0 if same else 1
    OUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    counts = document["counts"]
    print(f"RIGHTS_REGISTRY=WRITTEN {OUT.relative_to(REPO)} subjects={counts['subjects']} "
          f"adjudicated={counts['adjudicated']} awaiting={counts['awaiting_adjudication']} "
          f"blocked={counts['blocked_pending_owner']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
