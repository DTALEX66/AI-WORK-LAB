#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DESIGN-LAB canonical verifier entry (DL-MIG-011).

Aggregates the DESIGN-LAB verification chain under one entrypoint:
integration-assistance, product manifest, runtime contracts, visual scoring,
release evidence, source registry, v2 protocols and v21 visual quality.
"""
from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
from pathlib import Path


def run_child(command: list) -> subprocess.CompletedProcess:
    """Run a verifier under a deterministic text contract.

    The parent decodes child output as UTF-8 and tells the child to emit UTF-8, so the
    chain no longer depends on the machine locale. Before this, a child that printed
    Chinese under a cp936 parent produced UnicodeDecodeError inside the parent's own
    subprocess call: the chain then died with `NoneType has no attribute strip` and
    reported nothing about the other sixty steps. Reproduced by running this script
    with PYTHONIOENCODING=utf-8 (exit 1) versus without it (exit 0). A gate that dies
    while verifying hides every result behind it, so this is fail-closed by reporting
    the step rather than by crashing.
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        return subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env)
    except OSError as exc:
        return subprocess.CompletedProcess(command, 3, "", f"could not start: {exc}")

SCRIPTS = [
    "verify_identity_gate.py",
    # Packaging provenance, added after the owner audit at 7671ec70: the wheel force-includes repo
    # paths the published sdist did not carry, so the distribution could not rebuild its own wheel
    # (`FileNotFoundError: Forced include not found: …/design-lab/domain-packs`) while CI stayed
    # green -- it built from the checkout and never from the sdist.
    "verify_sdist_packaging.py",
    # The ledger's own contract: select a schema BY the ledger's schemaVersion, fail hard when
    # a version names no schema file (that is exactly how r5-v1 shipped without a contract for
    # a month), and keep schema and data accountable in both directions.
    "verify_ledger_schema_pairing.py",
    "verify_ledger_subject_binding.py",
    # Every test module has to run its own tests when executed as a file and import its own paths.
    # 17 of them had no `unittest.main()` guard (exit 0, zero tests run) and one imported a package
    # that only reached sys.path because a neighbour inserted it first -- both invisible under
    # discovery, which is the only way CI runs them.
    "verify_test_selfsufficiency.py",
    # Which of the 21 declared objects does product code actually validate against? The model reads
    # like a capability list; five of its schemas are loaded by product code, ten only by verifier
    # scripts and six by nothing at all, and the gate pins that per object so it cannot quietly grow.
    # Counting is done on executable text: a docstring that names a schema documents it, and since
    # 2026-10-08 prose no longer moves a bucket.
    "verify_object_model_backing.py",
    # Every *.template.json is what a person copies to make a real record. All three in the
    # repository were broken on 2026-10-08 -- one pointed outside the checkout, one was rejected
    # three times by the schema it names, one named no contract -- and no gate could see any of
    # it, so the honest "fill in the blanks and submit" workflow shipped an invalid document.
    "verify_template_contracts.py",
    # CI runs this one directly; it was missing from the aggregate, so a local bound run
    # could go green while the vocabulary contract was broken. That is exactly how a UI
    # change on 2026-10-08 passed every gate I ran and still broke canonical-verify.
    "verify_state_vocabularies.py",
    "verify_project_drift.py",
    "verify_knowledge_lifecycle.py",
    "verify_design_kernel.py",
    "verify_design_memory.py",
    "verify_quality_gate.py",
    "verify_reference_e2e.py",
    "verify_collection_pipeline.py",
    "verify_provider_spi.py",
    "verify_aesthetic_rules.py",
    "verify_design_ir.py",
    "verify_production_preflight.py",
    # The preflight verdicts the product emits are compared, on live payloads, against
    # design-lab/schemas/artifact-preflight.schema.json. Without this in the aggregate a
    # local bound run could go green while the four-word verdict vocabulary drifted --
    # this is the same class of hole as the vocabulary gate being CI-only.
    "verify_artifact_preflight_contract.py",
    # Four surfaces got the same question wrong in one session -- "which ACTIVE row is the
    # current version of this asset" -- because publish_version never demotes replaced
    # bytes. Each is fixed; this is the check that keeps a fifth reader from being written.
    "verify_current_version_rule.py",
    # Which contract schemas the product actually honours, and which route payload
    # versions really exist in an emitter. Both were written from payloads captured off
    # a live make_server socket, and both audit the committed ledger, so they must run
    # where every other ledger gate runs instead of living in a doc nobody executes.
    "verify_contract_bindings.py",
    "verify_route_payload_contracts.py",
    # The two gates above judge the service against its ledger and its payload schemas; neither
    # asks whether the page calls a path the service still serves. A renamed route could keep
    # every backend gate green while the view kept fetching the old path, so the TypeScript call
    # sites and the ROUTES table are compared in both directions (unserved call red, unreached
    # route red or named with a measured reason).
    "verify_workbench_route_calls.py",
    # 2026-10-08: the RIGHTS gate had a 74-subject requirements list, a hand-written band
    # table claiming to classify it, and a `counts` block nothing recomputed. An unclassified
    # licence state fell into a WARNING, so `READY_FOR_HANDOFF` was reachable over a position
    # nobody had ruled on. The band is now fail-closed and this re-checks the table against
    # the file, recomputes the summary, and resolves every cited provenance path.
    "verify_rights_registry.py",
    # The Workbench describes its own coverage in VIEW_NOT_OPEN and CAPABILITY_REGISTRY, and
    # nothing compared that text with the routes the service dispatches. It went stale the week
    # the research store landed: the slot still told the operator no route persisted conclusions.
    # This is the check that makes the self-description an assertion instead of a note.
    "verify_capability_self_description.py",
    # DL-FINAL-T07 (2026-10-11): a handful of external sources were actually read and their
    # method distilled into packages/capabilities/selected-sources.json. Two lies are easy
    # there -- treating a star count as a quality signal, and treating "we registered the
    # repo" as "we integrated the capability" -- so the record's revision, licence and
    # removal path are re-read from the candidate taxonomy, its landing modes are graded
    # against the real files and the adapter registry, and its execution qualification is
    # capped by the vocabulary capability-status.json publishes.
    "verify_selected_source_adaptation.py",
    "verify_experience_corpus.py",
    "verify_design_actions.py",
    "verify_tool_action_plan.py",
    "verify_golden_contracts.py",
    "verify_tool_write_protocols.py",
    "verify_branch_inventory.py",
    "verify_repository_size.py",
    # Task-document states (DL-REC-29, 2026-10-08): before this, authority-index only
    # classified by globs plus a current list, so 22 task packs under docs/taskpacks
    # sat in the unclassifiedFallback forever and "next round cannot find the task"
    # stayed possible. This gate requires a declared state for every tracked task
    # document, exactly one dispatch entry equal to the index's currentIntegrated, and
    # fails when this registry contradicts the index instead of letting two truths drift.
    "verify_task_document_states.py",
    "../../scripts/verify_current_execution.py",
    # DESIGN.md §2 says a new stacking layer has to be registered before it is used. Until
    # this verifier existed nothing checked it, so the rule was a sentence and any bare
    # `z-index` could ship. Values and selectors are derived from style.css, which makes the
    # table and the stylesheet one fact instead of two.
    "verify_ui_layering.py",
    "verify_dtcg_tokens.py",
    "verify_extraction_chain.py",
    "verify_federation_e2e.py",
    "verify_federation_review.py",
    "verify_quality_pipeline.py",
    "verify_review_surface.py",
    "integrations/hosts/open-design/verifier/verify_open_design_host_adapter.py",
    "verify_product_manifest_v3.py",
    "verify_runtime_contracts_v3.py",
    "verify_visual_scoring_v3.py",
    "verify_source_registry.py",
    # The other half of the vendor lock. `verify_source_registry.py` convicts ABSENT_FROM_GIT
    # rows that nobody declared; 37 further rows are LOCAL_CACHE_ONLY, i.e. their bytes exist
    # only in `.project-local/cache/vendor/` on one machine, so CI can never read them. Those
    # roots now carry a committed per-file manifest, and this gate proves each manifest hashes
    # to the digest the lock records -- so "we hold these 37 trees" stops being a claim about
    # somebody's disk. Runs with no arguments: the check reads repository state only.
    "verify_vendor_manifests.py",
    # Tracked projections that publish a subject field. `git("rev-parse HEAD")` as one argv
    # element is rejected by git, the helper returns empty stdout, and the field is written as
    # "" -- nine records were in that state with nothing checking it. The gate grades every
    # `subject_sha`/`subjectSha` under reports/current and design-lab/config against a shrinking
    # debt register, and refuses the call shape itself so a tenth cannot appear.
    "verify_report_subject_binding.py",
    # Each tracked projection that has a read-only re-check form gets re-checked here, in one place,
    # against its own record -- the gate that was missing when `deepseek_language_inventory.py
    # --check` had been red for weeks without a single runner. Three records are declared
    # exclusions because their re-check passes on the generating machine and fails on a clean
    # checkout of the same commit; the reasons live in the gate, and it runs no writer form.
    "verify_projection_freshness.py",
    "verify_v2_protocols.py",
    "verify_visual_quality_v21.py",
    "verify_style_master_method.py",
    "verify_capability_evidence_v4.py",
    "verify_comfyui_gate.py",
    "verify_sbom.py",
    "verify_adapter_registry.py",
    "verify_adapter_matrix.py",
    "verify_benchmark_registry.py",
    "verify_evidence_cards.py",
    "verify_asset_governance.py",
    "verify_external_assets_index.py",
    "verify_reconstruction_pipeline.py",
    "verify_reconstruction_security.py",
    "verify_reconstruction_golden_corpus.py",
    "verify_illustrator_reconstruction_adapter.py",
    "verify_photoshop_reconstruction_adapter.py",
    "verify_reconstruction_bundle.py",
    "verify_host_e3_evidence.py",
    "verify_control_capability_matrix.py",
    "verify_adapter_locator_audit.py",
    "verify_execution_path_gate.py",
    "verify_quality_record.py",
    "verify_readiness_host_matrix.py",
    "verify_context_integrity.py",
]

# Release-time gate: invoked separately with a release-evidence file argument.
# Kept out of the daily chain because it requires evidence input and must fail
# closed (non-zero) when no exact-SHA evidence is provided.
RELEASE_VERIFIER = "verify_release_evidence.py"
RECONSTRUCTION_RELEASE_VERIFIER = "verify_reconstruction_release.py"
# Batch F-3 (audit P1-CI) adds design-lab/scripts/verify_release_preflight.py:
# the real GitHub API readback gate (tag->SHA identity, CI conclusion, artifact
# download+sha256, release assets, checksums). It is deliberately NOT appended to
# SCRIPTS: it needs a tag, a token and the network, and it reports INCOMPLETE
# (non-zero) when any of those is missing, so running it inside this daily chain
# would turn an unprovable release into a red structural gate. release-gate.yml
# invokes it as its own step for tag refs, like RELEASE_VERIFIER above.
# Batch F-4 adds verify_host_e3_evidence.py — and it IS in SCRIPTS, unlike the
# two release-time verifiers: its default run reads the convention directory
# .project-local/task-artifacts/host-e3/, which is absent in a clean checkout,
# so it reports HOST_E3=NO_RECORD and exits 0. It only turns red when someone
# commits a fake/host-E3 record that fails its checks (schema contract,
# approver, boundTreeSha ancestry, artifact sha256) — exactly the
# fabricated-E3 case that should fail the gate daily.
# P1-CONTROL-SPIKE adds verify_control_capability_matrix.py — also in SCRIPTS:
# its default run validates the tracked capability routing declaration
# (design-lab/config/control-capability-matrix.json) against its schema and
# the fail-closed rules (supported=true requires evidence_level>=E2 +
# qualified_sha; no_bypass_license must be true; computer-use reachability
# requires a truth layer; matrix must cover browser + minimax-design). The
# matrix itself is honest (Adobe/MiniMax all supported=false/E0), so a clean
# checkout reports PASS and exits 0. It only turns red if someone commits a
# matrix that declares a capability outrunning its evidence or bypasses
# licensing — the "能点软件≠集成" trap this batch closes.
# DL-CLOUDAUDIT-H001 adds design-lab/scripts/verify_ci_artifact_proof.py:
# the main-branch CI artifact proof (real GitHub API readback of this run's
# own uploads: run/SHA identity, /actions/runs/<id>/artifacts query,
# download + sha256, bound proof record). It is deliberately NOT appended to
# SCRIPTS, for the same reason as verify_release_preflight.py above: it
# needs a GITHUB_TOKEN and live network, and it reports INCOMPLETE
# (non-zero) whenever the upload has not been indexed yet, so running it in
# this daily/structural chain would turn a re-queryable lag into a red
# gate. canonical-verify.yml invokes it as its own non-required
# ci-artifact-proof job (additive, on top of the existing required checks;
# H003 promotion to a required check stays an owner step).

# E1 确定性检查（DL-QLT-001 / DL-PRD-001），以参数化方式运行
EXTRA_CHECKS = [
    (
        "jury-anti-slop",
        [
            "quality/jury/check_anti_slop.py",
            # scan design-lab/ (resolved absolute below), skipping vendored/template trees
            ".",
            "--skip-prefixes",
            "templates/,evals/,exports/,domain-packs/uiux-design/benchmarks/,design-systems/,docs/history/,reports/history/",
        ],
    ),
]

def resolve_script(name: str, root: Path, repo_root: Path) -> Path:
    """Where a SCRIPTS entry lives.

    Verifiers inside `design-lab/scripts/` resolve relative to the scripts dir; host-adapter
    verifiers live outside it (DL-ADP-OD-001) and resolve relative to the repository root, and
    the `integrations/` ones moved to the repo-root-level tree after DL-DIR-MIG-R1. Factored out
    so the registry record and the run cannot disagree about which file a name means.
    """
    if name.startswith(("adapters/", "integrations/")):
        script = repo_root / "design-lab" / name
        if not script.exists():
            script = repo_root / name
        return script
    return root / name


def resolve_extra(args: list, root: Path) -> tuple:
    """The script and the literal arguments an EXTRA_CHECKS entry runs with."""
    repo_root_dir = root.parent.parent
    script = (repo_root_dir / "packages" / "capabilities" / args[0]
              if args[0].startswith("quality/") else root.parent / args[0])
    resolved = [str(repo_root_dir / "design-lab") if a == "." else a for a in args[1:]]
    return Path(script), resolved


def emit_registry(root: Path, repo_root: Path) -> int:
    """One line per check: the command the chain runs, its inputs, its args, its result target.

    D05 (2026-10-15). The chain owned a list of 74 names and nothing recorded what each one is
    invoked with, so "does this step duplicate that verifier?" had to be answered by reading two
    files side by side -- which is how a redundant invocation survives. This is printed rather
    than committed on purpose: a committed copy of a list the chain already owns is one more
    thing that can disagree with the chain.
    """
    for index, name in enumerate(SCRIPTS, 1):
        script = resolve_script(name, root, repo_root)
        rel = script.relative_to(repo_root).as_posix() if script.is_absolute() else str(script)
        print(f'CHAIN_CHECK {index:02d} name={name} '
              f'command="python {rel}" inputs="{rel}" args=[] '
              f'target=exit_code+first_summary_line present={script.exists()}')
    for name, args in EXTRA_CHECKS:
        script, resolved = resolve_extra(args, root)
        rel = script.relative_to(repo_root).as_posix() if script.is_absolute() else str(script)
        print(f'CHAIN_CHECK -- name={name} command="python {rel} {" ".join(resolved)}" '
              f'inputs="{rel}" args={resolved} target=exit_code+last_stdout_line '
              f'present={script.exists()}')
    print(f'CHAIN_REGISTRY=EMITTED scripts={len(SCRIPTS)} extra={len(EXTRA_CHECKS)} '
          f'total={len(SCRIPTS) + len(EXTRA_CHECKS)}')
    return 0


#: Distribution name -> import name, for the declared dependencies whose two names differ.
#: The required SET is read from pyproject.toml rather than repeated here, so this table only
#: translates a name and never decides on its own what the project needs.
_IMPORT_NAME_ALIASES = {"pillow": "PIL", "scikit-image": "skimage"}


def missing_declared_dependencies(repo_root: Path) -> list:
    """Which of the package's own declared dependencies this interpreter cannot import.

    Why this exists: `run_child` spawns every verifier with `sys.executable`, so the whole
    chain silently runs under whichever python invoked it. On a machine where the project
    venv was not used, 17 verifiers that import `jsonschema` each failed with ModuleNotFound
    and the aggregate reported `VERIFY_DESIGN_LAB=OK total=76 failed=29` on the SAME commit
    that reports `failed=0` under `.venv`. Twenty-nine product regressions is a lie; the
    truth is one wrong interpreter, and a reader has no way to tell from that line. Refusing
    with a named cause attributes the failure at its raise site instead of laundering it into
    the step count.
    """
    import tomllib

    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return []
    with open(pyproject, "rb") as handle:
        declared = tomllib.load(handle).get("project", {}).get("dependencies", [])
    missing = []
    for spec in declared:
        name = re.split(r"[<>=!;\[\s]", str(spec).strip(), maxsplit=1)[0].lower()
        module = _IMPORT_NAME_ALIASES.get(name, name.replace("-", "_"))
        try:
            importlib.import_module(module)
        except Exception:  # any failure to import is a missing dependency for this purpose
            missing.append(f"{spec} (import {module})")
    return missing


def main() -> int:
    root = Path(__file__).resolve().parent
    results: list[tuple[str, int]] = []
    repo_root = root.parent.parent
    if '--emit-registry' in sys.argv[1:]:
        return emit_registry(root, repo_root)
    missing = missing_declared_dependencies(repo_root)
    if missing:
        print(f"VERIFY_DESIGN_LAB=REFUSED interpreter={sys.executable}")
        for item in missing:
            print(f"  MISSING_DEPENDENCY {item}")
        print(f"VERIFY_DESIGN_LAB=REFUSED the declared dependencies above are not importable in "
              f"this interpreter, so the {len(SCRIPTS) + len(EXTRA_CHECKS)} steps below would "
              f"report the missing import as a "
              f"product failure. Run the chain with the project venv "
              f"(.venv/Scripts/python.exe on Windows, .venv/bin/python elsewhere).")
        return 2
    for name in SCRIPTS:
        script = resolve_script(name, root, repo_root)
        if not script.exists():
            print(f"MISSING {name} (required verifier absent)")
            results.append((name, 2))
            continue
        print(f"\n===== {name} =====")
        r = run_child([sys.executable, str(script)])
        tail = (r.stdout or "").strip().splitlines()
        summary = next((line for line in reversed(tail) if line.startswith(("VERIFY_", "STYLE_MASTER_METHOD=", "ADAPTER_", "BENCHMARK_", "EVIDENCE_", "PASS", "FAIL"))), "")
        print(summary)
        if r.returncode != 0:
            # print the full failing verifier output for diagnosis (incl. tracebacks)
            print((r.stdout or "").strip())
        results.append((name, r.returncode))
        if r.returncode != 0 and (r.stderr or "").strip():
            print((r.stderr or "").strip())

    for name, args in EXTRA_CHECKS:
        print(f"\n===== {name} =====\n")
        script_arg, resolved_args = resolve_extra(args, root)
        r = run_child([sys.executable, str(script_arg), *resolved_args])
        tail = (r.stdout or "").strip().splitlines()
        summary = tail[-1] if tail else "(no output)"
        print(summary)
        if r.returncode != 0:
            for line in tail[:-1]:
                print(f"  {line}")
        results.append((name, r.returncode))

    failed = [name for name, code in results if code != 0]
    ok = not failed
    # write verify-chain marker ONLY on full pass; on failure remove/leave FAIL.
    # root here = design-lab/scripts/; repo root = root.parent.parent
    # Fail-closed: marker write / HEAD resolution failures must not silently
    # turn a pass into OK without the marker (Codex review finding 6).
    try:
        repo_root = root.parent.parent
        head = run_child(["git", "-C", str(repo_root), "rev-parse", "HEAD"]).stdout.strip()
        if not head:
            raise RuntimeError("git rev-parse HEAD returned empty")
        marker = repo_root / "design-lab" / "config" / ".verify-chain-ok"
        if ok:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(f"ok {head}\n", encoding="utf-8")
        else:
            if marker.exists():
                marker.write_text(f"FAIL {head}\n", encoding="utf-8")
    except Exception as exc:
        results.append(("verify-chain-marker", 1))
        failed.append("verify-chain-marker")
        ok = False
        print(f"verify-chain-marker: FAIL ({exc})")
    print(f"\nVERIFY_DESIGN_LAB={'OK' if ok else 'FAIL'} total={len(results)} failed={len(failed)}")
    for name, code in results:
        print(f"  {'PASS' if code == 0 else 'FAIL'} {name}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
