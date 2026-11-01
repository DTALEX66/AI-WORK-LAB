#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-H040 — evidence level discipline gate.

DeepSeek may independently prove E0 (declared) and E1 (structural), and E2 only
for a non-professional host it actually ran in a controlled runtime. It may never
claim Adobe E3, OpenDesign E3, ComfyUI design E3, Blender E3 or a Human Jury E4.

This gate scans every place an evidence level is declared and separates three
cases:

* **allowed** — E0/E1 anywhere; E2 where the artefact names the controlled run;
  E3 for a professional host only when the claim is explicitly historical and
  carries runtime identity and artifact paths, which is what
  `verify_adapter_matrix.py` already enforces for its two allowed adapters;
* **historical** — an E3 claim labelled as historical, kept as evidence and not
  presented as a current capability;
* **overclaim** — anything else, which fails the gate.

Writes reports/current/EVIDENCE-LEVEL-AUDIT.json.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# Run standalone from any cwd: the ladder is authored in src/, not copied here.
sys.path.insert(0, str(REPO / "src"))
from design_lab.governance.evidence_levels import EVIDENCE_LEVELS as LADDER  # noqa: E402

OUT = REPO / "reports/current/EVIDENCE-LEVEL-AUDIT.json"
TASK_KEY = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-H040"
# Hosts whose E3 may only ever be claimed by Codex, with a real run.
CODEX_ONLY = ("photoshop", "illustrator", "premiere", "after effects", "media encoder",
              "indesign", "blender", "opendesign", "open design", "minimax design")
FORBIDDEN_BY_DEEPSEEK = ("E3", "E4", "E5")
HISTORICAL_MARKERS = ("historical", "superseded", "pre-convergence", "no current-tree requalification",
                      "not a current capability")
LEVEL_PATTERN = re.compile(r'"level"\s*:\s*"(' + '|'.join(LADDER) + r')"')
# A section that exists to forbid a claim is not making one. The taskpack itself has
# such a section ("what DeepSeek may never claim"), and the evidence packet repeats it,
# so a denial list read as a claim is a false positive that would fail the gate on the
# very document that states the prohibition.
DENIAL_HEADINGS = re.compile(r"(not claimed|do not claim|must not claim|never claim|"
                             r"forbidden|do-not-claim|禁止宣称|不得宣称|不可宣称)", re.I)


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip()


def tracked() -> list:
    return [line for line in git("ls-files").splitlines() if line.strip()]


NON_CLAIM_MARKERS = ("not_executed", "not executed", "deferred", "requires", "required",
                     "readiness", "plan", "target", "example", "would", "must be proved",
                     "is required", "pending", "unverified", "not a current capability",
                     "no runtime was started", "invalidated", "must not be used",
                     "not be used to promote", "candidate record", "historical",
                     "before it may", "condition", "ladder", "promotion")
ACHIEVEMENT_VERBS = ("verified", "passed", "achieved", "integrated", "produced", "executed",
                     "validated", "accepted")
# Self-test fixtures: the gate must fail on these, or it proves nothing.
SELF_TEST = [
    ({"path": "reports/current/DEEPSEEK-X.json", "level": "E3", "host": "photoshop",
      "historical": False, "runtime_identity": False, "artifact_paths": False,
      "agent_authored": True, "professional_host": "photoshop", "jury": False, "dated": False},
     "OVERCLAIM", "a DeepSeek artifact claiming Photoshop E3"),
    ({"path": "design-lab/readiness/model-radar.json", "level": "E4", "host": None,
      "historical": False, "runtime_identity": True, "artifact_paths": True,
      "agent_authored": False, "professional_host": None, "jury": True, "dated": True},
     "OVERCLAIM", "an E4 jury claim"),
    ({"path": "integrations/adapter-registry.json", "level": "E3", "host": "blender",
      "historical": False, "runtime_identity": False, "artifact_paths": False,
      "agent_authored": False, "professional_host": "blender", "jury": False, "dated": False},
     "OVERCLAIM", "a Blender E3 claim without a run"),
    ({"path": "integrations/adapter-registry.json", "level": "E3", "host": "comfyui",
      "historical": True, "runtime_identity": True, "artifact_paths": True,
      "agent_authored": False, "professional_host": None, "jury": False, "dated": True},
     "HISTORICAL_EVIDENCE_KEPT", "a dated E3 with runtime identity and artifacts"),
    ({"path": "design-lab/readiness/model-radar.json", "level": "E1", "host": None,
      "historical": False, "runtime_identity": False, "artifact_paths": False,
      "agent_authored": True, "professional_host": None, "jury": False, "dated": False},
     "ALLOWED", "a structural claim"),
]


def _enclosing_objects(document, wanted_levels):
    """Every dict that declares a level, with its own serialization as context."""
    found = []

    def walk(node, context):
        if isinstance(node, dict):
            level = node.get("level")
            own = context or node.get("adapter_id") or node.get("id") or node.get("tool")
            if level in wanted_levels:
                found.append({"level": level, "context": json.dumps(node, ensure_ascii=False),
                              "identity": own})
            for key, value in node.items():
                walk(value, own)
        elif isinstance(node, list):
            for value in node:
                walk(value, context)

    walk(document, None)
    return found


def scan_json_claims(rel: str, text: str) -> list:
    try:
        document = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []
    claims = []
    for item in _enclosing_objects(document, FORBIDDEN_BY_DEEPSEEK):
        context = item["context"].lower()
        claims.append({
            "path": rel,
            "level": item["level"],
            "subject": item["identity"],
            "host": next((name for name in CODEX_ONLY if name in context), None),
            "historical": any(marker in context for marker in HISTORICAL_MARKERS),
            "runtime_identity": bool(re.search(r"task_ids|runtime_id|prompt_id", item["context"], re.I)),
            "artifact_paths": bool(re.search(r"artifact_paths|evidence/", item["context"], re.I)),
        })
    return claims


def scan_markdown_claims(rel: str, text: str, declared_non_claims: list | None = None) -> list:
    """A document that describes the ladder, plans a level, or forbids a claim is not
    making one."""
    claims = []
    in_fence = False
    heading = ""
    lines = text.splitlines()
    low, high = LADDER[0][1:], LADDER[-1][1:]
    range_pattern = re.compile(rf"E[{low}-{high}]\s*[-–—]\s*E[{low}-{high}]")
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith("#"):
            heading = line.strip()
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        bare = range_pattern.sub("LADDER", line)
        for level in FORBIDDEN_BY_DEEPSEEK:
            if not re.search(rf"\b{level}\b", bare):
                continue
            if DENIAL_HEADINGS.search(heading):
                # Recorded, not silently dropped: the gate reports how many lines it
                # read as prohibitions so the exemption is auditable.
                if declared_non_claims is not None:
                    declared_non_claims.append({"path": rel, "heading": heading,
                                                "line": number, "text": line.strip()[:140]})
                continue
            window = " ".join(lines[max(0, number - 3):number + 3]).lower()
            if any(marker in window for marker in NON_CLAIM_MARKERS):
                continue
            # The achievement verb must be on the same line as the level: a
            # paragraph about the ladder elsewhere is not a claim.
            if not any(verb in line.lower() for verb in ACHIEVEMENT_VERBS):
                continue
            claims.append({"path": rel, "level": level, "subject": None, "host": None,
                           "historical": any(marker in window for marker in HISTORICAL_MARKERS),
                           "runtime_identity": bool(re.search(r"task_?ids|runtime_?id|prompt_?id",
                                                              window)),
                           "artifact_paths": bool(re.search(r"artifact|evidence/", window)),
                           "line": number, "text": line.strip()[:140]})
    return claims


# The gate audits the *current* claim surface. Historical records are explicitly
# out of scope: the taskpack forbids rewriting them, and a 2026-08 handoff that
# discusses the ladder is not a claim about today's capability.
CLAIM_SURFACE = (
    "integrations/adapter-registry.json",
    "integrations/generators/",
    "integrations/hosts/",
    "design-lab/readiness/",
    "design-lab/config/",
    "product-manifest.json",
    "reports/current/",
)
OUT_OF_SCOPE_PREFIXES = ("docs/history/", "reports/history/", "docs/taskpacks/")
SELF_OUTPUT = "reports/current/EVIDENCE-LEVEL-AUDIT.json"
AGENT_AUTHORED = ("reports/current/DEEPSEEK-",)
PROFESSIONAL_HOSTS = ("photoshop", "illustrator", "premiere", "after effects", "media encoder",
                      "indesign", "blender", "opendesign", "open design", "minimax design")
DATED = re.compile(r"20\d\d-\d\d-\d\d")


def in_claim_surface(rel: str) -> bool:
    if rel.startswith(OUT_OF_SCOPE_PREFIXES):
        return False
    if rel == SELF_OUTPUT:
        # Self-reference: the gate's own report lists the claims it found, so scanning
        # it re-counts them as new claims and the artefact doubles on every run
        # (4 -> 8). An INDEPENDENT AUDIT caught the non-idempotence.
        return False
    return any(rel == prefix or rel.startswith(prefix) for prefix in CLAIM_SURFACE)


def scan_claims(declared_non_claims: list | None = None) -> list:
    claims = []
    for rel in tracked():
        if not in_claim_surface(rel):
            continue
        path = REPO / rel
        if path.suffix not in {".json", ".md"}:
            continue
        try:
            if path.stat().st_size > 3_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not any(level in text for level in FORBIDDEN_BY_DEEPSEEK):
            continue
        found = (scan_json_claims(rel, text) if path.suffix == ".json"
                 else scan_markdown_claims(rel, text, declared_non_claims))
        for claim in found:
            claim["agent_authored"] = rel.startswith(AGENT_AUTHORED)
            claim["dated"] = bool(DATED.search(claim.get("context", "") or claim.get("text", "")
                                               or ""))
            context = (claim.get("context") or claim.get("text") or "").lower()
            claim["professional_host"] = next((name for name in PROFESSIONAL_HOSTS
                                               if name in context or name == (claim.get("host") or "")),
                                              None)
            claim["jury"] = "jury" in context or "humanjury" in context.replace(" ", "")
        claims.extend(found)
    return claims


def classify(claim: dict) -> dict:
    level = claim["level"]
    if level in {"E0", "E1"}:
        verdict = "ALLOWED"
    elif level == "E2":
        verdict = "ALLOWED" if claim["runtime_identity"] else "REVIEW_NO_RUNTIME_IDENTITY"
    elif level in {"E4", "E5"}:
        # Independent acceptance and release are never an agent's to claim.
        verdict = "OVERCLAIM"
    elif claim["agent_authored"]:
        # A DeepSeek-authored artifact may reference a recorded run (naming the
        # evidence path and a date) but never assert the level as its own result,
        # and never for a professional host.
        if claim["professional_host"] or claim["jury"]:
            verdict = "OVERCLAIM"
        elif claim["artifact_paths"] and (claim["historical"] or claim["dated"]):
            verdict = "REFERENCES_RECORDED_EVIDENCE"
        else:
            verdict = "OVERCLAIM"
    elif claim["runtime_identity"] and claim["artifact_paths"] and (claim["historical"]
                                                                   or claim["dated"]):
        verdict = "HISTORICAL_EVIDENCE_KEPT"
    elif claim["professional_host"]:
        verdict = "OVERCLAIM"
    else:
        verdict = "OVERCLAIM"
    return {**claim, "verdict": verdict}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true",
                        help="prove the classifier still fails on a real overclaim")
    args = parser.parse_args(argv)
    if args.self_test:
        failures = []
        for fixture, expected, description in SELF_TEST:
            got = classify(dict(fixture))["verdict"]
            if got != expected:
                failures.append(f"{description}: expected {expected}, got {got}")
        # A do-not-claim section must not be read as a claim, or the gate fails on the
        # very document that states the prohibition.
        denial = ("## What is NOT claimed\n\n"
                  "* Photoshop integrated E3\n"
                  "* Release ready\n")
        if scan_markdown_claims("reports/current/FAKE.md", denial, []):
            failures.append("a line under a do-not-claim heading was classified as a claim")
        recorded = []
        scan_markdown_claims("reports/current/FAKE.md", denial, recorded)
        if not recorded:
            failures.append("a do-not-claim line must still be counted and listed, not dropped")
        # The same line under an ordinary heading is a claim and must still be caught.
        affirmative = "## Status\n\n* Photoshop integrated E3\n"
        if not scan_markdown_claims("reports/current/FAKE.md", affirmative, []):
            failures.append("an unmarked E3 claim outside a denial section is no longer caught")
        print("EVIDENCE_LEVEL_SELF_TEST=" + ("PASS" if not failures else "FAIL"))
        for failure in failures:
            print("  FAIL", failure)
        return 0 if not failures else 1
    declared_non_claims: list = []
    claims = [classify(claim) for claim in scan_claims(declared_non_claims)]
    overclaims = [claim for claim in claims if claim["verdict"] == "OVERCLAIM"]
    reviews = [claim for claim in claims if claim["verdict"].startswith("REVIEW")]
    allowed = [claim for claim in claims if claim["verdict"] == "ALLOWED"]
    historical = [claim for claim in claims if claim["verdict"] == "HISTORICAL_EVIDENCE_KEPT"]
    references = [claim for claim in claims if claim["verdict"] == "REFERENCES_RECORDED_EVIDENCE"]
    document = {
        "schemaVersion": "design-lab/evidence-level-audit/v1",
        "task_key": TASK_KEY,
        "audited_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": git("rev-parse", "HEAD").strip(),
        "claim_surface": list(CLAIM_SURFACE),
        "out_of_scope": list(OUT_OF_SCOPE_PREFIXES),
        "scope_note": "historical records and superseded taskpacks are excluded: the taskpack "
                      "forbids rewriting them, and a past document that discusses the ladder is "
                      "not a claim about today's capability",
        "deepseek_may_claim": ["E0", "E1"],
        "deepseek_may_claim_with_a_controlled_run": ["E2"],
        "codex_only": list(CODEX_ONLY),
        "never_by_deepseek": ["Adobe E3", "OpenDesign E3", "ComfyUI design E3", "Blender E3",
                              "Human Jury E4"],
        "counts": {"claims_examined": len(claims), "allowed": len(allowed),
                   "historical_evidence_kept": len(historical),
                   "references_recorded_evidence": len(references), "review": len(reviews),
                   "overclaims": len(overclaims),
                   "declared_non_claims_examined": len(declared_non_claims)},
        "overclaims": overclaims,
        "review": reviews,
        "historical": historical,
        "references": references,
        "declared_non_claims": declared_non_claims[:20],
        "declared_non_claims_rule": "a line under a heading that forbids a claim (for example "
                                    "'What is NOT claimed') is a prohibition, not a claim; those "
                                    "lines are counted and listed here rather than classified",
        "verdict": "PASS" if not overclaims else "FAIL",
        "self_output_excluded": SELF_OUTPUT,
        "gate_is_not_vacuous": "run --self-test: the classifier must return OVERCLAIM for a "
                               "DeepSeek-authored Photoshop E3, an E4 jury claim and an "
                               "unbacked Blender E3, and HISTORICAL for a dated E3 with runtime "
                               "identity and artifacts",
    }
    if args.check:
        # Compare the classification itself, not only the counts: the earlier check
        # could not see a claim move between two verdicts.
        if not OUT.is_file():
            print("EVIDENCE_LEVELS=DRIFT missing " + OUT.name)
            return 1
        stored = json.loads(OUT.read_text(encoding="utf-8"))
        keys = ("overclaims", "review", "historical", "references")

        def classified(document):
            return sorted((c["path"], c["level"], c["verdict"])
                          for key in keys for c in document.get(key, []))

        if stored.get("counts") != document["counts"] or classified(stored) != classified(document):
            print("EVIDENCE_LEVELS=DRIFT classification changed since generation")
            return 1
        print("EVIDENCE_LEVELS=PASS (counts and every classified claim match)")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"EVIDENCE_LEVELS={document['verdict']} " + " ".join(f"{k}={v}" for k, v in
                                                               document["counts"].items()))
    for claim in overclaims:
        print(f"  OVERCLAIM {claim['level']} in {claim['path']} (host={claim['host']})")
    for claim in reviews:
        print(f"  REVIEW {claim['level']} in {claim['path']}")
    return 0 if not overclaims else 1


if __name__ == "__main__":
    raise SystemExit(main())
