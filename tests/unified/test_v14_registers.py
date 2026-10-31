# SPDX-License-Identifier: MIT
"""V14: the registers and packaged assets this rework now claims, checked as data.

Three claims were made in prose during the rework and prose cannot be audited, so
each is turned into a recomputation here:

* the source-coverage register must account for **every** non-ignored file in both
  read-only sources, with no row in a class that means "we did not look";
* the F01 disposition register must stay at the audited 198 registered-but-uncopied
  WORK paths, each with a digest and a stated reason;
* the two F06 gaps that were closable offline are closed in fact: the host bridge
  script must be reachable at the path the adapter probes and byte-identical to the
  source of truth, and the control plane must parse a YAML document instead of
  reporting `DOCUMENT_UNPARSEABLE`.
"""
from __future__ import annotations

import csv
import collections
import hashlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TARGET_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = str(TARGET_ROOT / ".venv" / "Scripts" / "python.exe")
WORK_SOURCE = TARGET_ROOT.parent / "WORK-LAB"
DESIGN_SOURCE = TARGET_ROOT.parent / "DESIGN-LAB"
BRIDGE_PACKAGED = (TARGET_ROOT / "domains" / "design" / "design_lab" / "resources"
                   / "adobe" / "photoshop-native-assemble.jsx")
BRIDGE_SOURCE_OF_TRUTH = (TARGET_ROOT / "integrations" / "hosts" / "adobe"
                          / "photoshop-reconstruction" / "legacy-assemble.jsx")

#: Classes that would mean the register did not actually decide anything.
UNEXPLAINED = {"", "SOURCE_UNREGISTERED", "COPIED_MISSING_IN_TARGET"}

#: The rows the adjudication ladder genuinely could not decide, enumerated by path.
#: This used to be 226 rows sharing one template reason and a guard test that only
#: looked for the literal word "owner" — that cannot fail, so it was not a check.
#: A row may join this set only by a deliberate edit here, and a row that leaves it
#: must be picked up by an authority-backed class instead.
PENDING_OWNER_DECISIONS = {
    "work": frozenset({
        "apps/observer/scripts/u19_webview_e2e.py",
        "apps/observer/scripts/usage_rollup.py",
        "apps/observer/scripts/write_artifact_receipt.py",
        "apps/observer/src/observer_evidence.py",
        "apps/observer/src/observer_runtime.py",
        "apps/observer/src/observer_state_classification.py",
        "apps/observer/src/observer_store.py",
        "integrations/archeaxis/contracts/open_design_client_seam.py",
        "integrations/archeaxis/contracts/promotion_contract.py",
        "scripts/audit/bundle_provenance.py",
        "scripts/audit/hud_strip_geometry_via_cdp.py",
        "scripts/audit/text_legibility_via_cdp.py",
        "scripts/audit/topbar_geometry_via_cdp.py",
        "scripts/maintenance/absorb_local_assets.py",
        "scripts/maintenance/converge_u02_runtime_paths.py",
        "scripts/maintenance/finish_tmp_tree_cleanup.py",
        "scripts/maintenance/record_documentation_drifts.py",
        "services/policy/universal_agent_core.py",
    }),
    "design": frozenset({
        "design-lab/core/__init__.py",
        "design-lab/core/commands.py",
        "design-lab/core/project_state.py",
        "design-lab/core/providers.py",
        "design-lab/core/quality_gate.py",
        "design-lab/core/user_modes.py",
        "design-lab/scripts/effective_evidence.py",
        "design-lab/scripts/resolve_open_design_locator.py",
        "scripts/amend_source_lock_presence.py",
        "scripts/archive_records.py",
        "scripts/collect_design_capability_candidates.py",
        "scripts/deepseek_test_gate_report.py",
        "scripts/generate_current_reports.py",
        "scripts/run_python_tests.py",
    }),
}

#: Classes that must each carry a resolvable ``file:line`` authority citation.
ADJUDICATED_CLASSES = {"UNREGISTERED_TARGET_PATH_PRESENT", "UNREGISTERED_EXCLUDED_CAPABILITY",
                       "UNREGISTERED_DEV_TOOLING"}
_CITATION = re.compile(r"^(.+?):(\d+)$")


def _read(csv_path: Path) -> list[dict]:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _coverage(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("coverage") / "source-coverage.json"
    completed = subprocess.run(
        [VENV_PYTHON, "-B", "-X", "utf8",
         str(TARGET_ROOT / "scripts" / "build_source_coverage.py"),
         "--json-out", str(out)],
        cwd=str(TARGET_ROOT), capture_output=True, text=True, timeout=3000,
        encoding="utf-8", errors="replace")
    assert completed.returncode == 0, completed.stderr[-2000:]
    return json.loads(out.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def coverage(tmp_path_factory) -> dict:
    return _coverage(tmp_path_factory)


def test_coverage_register_accounts_for_every_source_file(coverage):
    for label, repo in (("work", WORK_SOURCE), ("design", DESIGN_SOURCE)):
        document = coverage["repos"][label]
        listed = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=str(repo)).decode("utf-8").split("\0")
        files = sorted(x for x in set(listed) if x
                       and not {".mimosa", "__pycache__", ".pytest_cache", ".venv",
                                "node_modules"} & set(Path(x).parts)
                       and (repo / x).is_file())
        rows = _read(TARGET_ROOT / ("migration/source-coverage-" + label + ".csv"))
        assert sorted({row["path"] for row in rows}) == files, label
        assert document["reconciles"] is True, document["class_counts"]
        assert sum(document["class_counts"].values()) == document["rows"], label


def test_coverage_register_leaves_no_row_undecided(coverage):
    """"无未解释遗漏" as a falsifiable claim, not a substring match.

    The clause V01 checks has two halves. The first is that no row sits in a class
    that means "we did not look". The second, added on 2026-10-31, is that the
    remaining undecided population equals an enumerated set: 226 rows carrying one
    template reason passed the old assertion because that reason contained the
    literal word "owner", which is not a decision and was not a check.
    """
    for label in ("work", "design"):
        rows = _read(TARGET_ROOT / ("migration/source-coverage-" + label + ".csv"))
        for row in rows:
            assert row["class"], row
            assert row.get("reason") or row["class"].startswith("COPIED_VERIFIED"), row
            assert row["class"] not in UNEXPLAINED, row
            if row["class"] in ADJUDICATED_CLASSES:
                cites = [c.strip() for c in re.split(r";| → ", row.get("authority", ""))]
                assert cites and cites != [""], row
                for cite in cites:
                    match = _CITATION.match(cite)
                    assert match, (row["class"], cite)
                    authority = TARGET_ROOT / match.group(1)
                    assert authority.is_file(), (row["path"], cite)
                    lines = authority.read_text(encoding="utf-8-sig").splitlines()
                    number = int(match.group(2))
                    assert 0 < number <= len(lines), (row["path"], cite)
                    assert "AUTHORITY_NOT_FOUND" not in cite, row

        pending = [row for row in rows if row["class"] == "OWNER_DECISION_PENDING"]
        assert frozenset(row["path"] for row in pending) == PENDING_OWNER_DECISIONS[label], (
            label, sorted(frozenset(row["path"] for row in pending)
                          - PENDING_OWNER_DECISIONS[label]),
            sorted(PENDING_OWNER_DECISIONS[label]
                   - frozenset(row["path"] for row in pending)))
        assert len(pending) == len(PENDING_OWNER_DECISIONS[label]), label
        assert pending and all(row["path"].endswith(".py") for row in pending)
        # one row, one justification: no shared template may cover the population
        reasons = [row["reason"] for row in pending]
        assert len(set(reasons)) == len(reasons), [
            reason for reason in set(reasons) if reasons.count(reason) > 1][:3]
        for row in pending:
            assert row["reason"].count("待 owner 判定") == 1, row
            # the justification names this row's own bytes, not the class it fell into
            assert row["reason"].startswith("待 owner 判定（本行字节 "
                                            + row["source_sha256"][:12] + "）"), row
            assert "NONE（无现成权威覆盖此行）" in row["authority"], row
        adjudicated = [row for row in rows if row["class"] in ADJUDICATED_CLASSES]
        assert adjudicated, label
        # the register must say which population it adjudicated, per repo
        document = coverage["repos"][label]
        assert document["adjudicated_by_authority_count"] == len(adjudicated), label
        assert sorted(document["adjudicated_by_authority"]) == sorted(
            row["path"] for row in adjudicated), label
        assert document["pending_reason_duplicates"] == {}, document["pending_reason_duplicates"]
        assert document["pending_owner_decision_count"] == len(pending), label


def test_f01_register_separates_wired_from_merely_present():
    """The ``目标文件 exists`` claim is not a wiring claim, and is no longer one.

    ``git_collector.py`` sits in the target tree and imports cleanly, so the old
    assertion could never fail; the only ``git_collector`` in running code is an
    inline ``def`` inside ``collectors.py``. The register now carries the graph's
    answer per row, so this checks the answer rather than the file.
    """
    rows = _read(TARGET_ROOT / "migration/work-gap-disposition.csv")
    assert rows and {"运行面消费者", "消费者数"} <= set(rows[0]), list(rows[0])
    wired = [row for row in rows if row["去向类别"] == "MIGRATED_WIRED"]
    for row in wired:
        consumers = [c for c in row["运行面消费者"].split(";") if c]
        assert consumers, row
        assert int(row["消费者数"]) == len(consumers), row
        assert all((TARGET_ROOT / c).is_file() for c in consumers), row
    for row in rows:
        if row["去向类别"] == "MIGRATED_PRESENT_UNWIRED":
            assert row["运行面消费者"] == "" and row["消费者数"] == "0", row
            assert "没有找到任何 importer" in row["判定依据"], row
    by_path = {row["原路径"]: row for row in rows}
    false_claim = "packages/client-neutral-core/scripts/git_collector.py"
    assert by_path[false_claim]["去向类别"] == "MIGRATED_PRESENT_UNWIRED", by_path[false_claim]
    assert by_path[false_claim]["目标文件"] == "domains/work/orchestration/git_collector.py"
    assert (TARGET_ROOT / "domains/work/orchestration/git_collector.py").is_file(), \
        "downgraded does not mean deleted: the bytes stay, the claim changes"


def test_coverage_gap_rows_match_the_f01_register(coverage):
    """The two registers must not disagree about the same file.

    The counts used to be pinned to the literal the audit recorded (198). That made a real
    closure look like a breakage: when ``adapter_conformance.py`` was actually migrated, the
    gap set legitimately became 197 and four remembered numbers went red at once. The check
    is now the one that matters -- the two builders, which read different inputs, must agree
    with each other and with the register file -- with a floor so an emptied population can
    never pass, and with the distance from the audited baseline stated rather than assumed.
    """
    disposition = _read(TARGET_ROOT / "migration/work-gap-disposition.csv")
    check = coverage["cross_check"]
    assert check["f01_register_reports_work_python_gaps"] == len(disposition), check
    assert check["registered_gap_python_paths_by_repo"]["work"] == len(disposition), check
    assert check["gap_delta_since_audit"] == 198 - len(disposition), check
    assert 190 <= len(disposition) <= 198, (
        "去向登记只剩 %d 行：population 缩水到这个程度只会是计算口径坏了，不是缺口被关掉"
        % len(disposition))
    coverage_gaps = {row["path"] for row in
                     _read(TARGET_ROOT / "migration/source-coverage-work.csv")
                     if row["class"] == "REGISTERED_GAP" and row["path"].endswith(".py")}
    assert coverage_gaps == {row["原路径"] for row in disposition}
    for row in disposition:
        assert len(row["来源sha256"]) == 64, row
        assert row["去向类别"] and row["判定依据"], row


def test_registered_non_python_gaps_state_where_the_file_actually_is(coverage):
    """"Not in the copy manifest" is not "absent" — the register has to say which.

    Two of the seven registered non-``.py`` gaps are WORK registry files the F01
    module migration placed at this repository's own ``config/`` root; the rest are
    governance documents and a frontend file. Reporting all of them as gaps would
    be the same mistake the audited close-out made in reverse.
    """
    rows = [row for row in _read(TARGET_ROOT / "migration/source-coverage-work.csv")
            if row["class"] == "REGISTERED_GAP" and not row["path"].endswith(".py")]
    assert len(rows) == 7, [row["path"] for row in rows]
    by_path = {row["path"]: row for row in rows}
    for path in ("config/adapter-registry.json", "config/capability-matrix.json"):
        assert by_path[path]["disposition"].startswith("PRESENT_IN_TARGET"), by_path[path]
        target = TARGET_ROOT / by_path[path]["disposition_target"]
        assert target.is_file(), path
        source = WORK_SOURCE / path
        same = (hashlib.sha256(target.read_bytes()).hexdigest()
                == hashlib.sha256(source.read_bytes()).hexdigest())
        assert same == (by_path[path]["disposition"] == "PRESENT_IN_TARGET"), by_path[path]


def test_duplicate_candidates_are_recomputable_and_deferrals_carry_a_reason():
    """V01's second half — "重复项与延期有理由" — as two checks that can fail.

    Nothing asserted this before: the duplicate register was prose the suite never
    opened, so "identical bytes, therefore a duplicate" could have been stale or
    wrong and the run would still have been green. Each group's digest is recomputed
    from both read-only sources here, and each deferral row must name what it keeps.
    """
    document = json.loads((TARGET_ROOT / "migration" / "duplicate-candidates.json")
                          .read_text(encoding="utf-8"))
    groups = document["groups"]
    assert len(groups) == document["group_count"], "group_count is not the number of groups"
    sources = json.loads((TARGET_ROOT / "migration" / "sources.json").read_text(encoding="utf-8"))
    assert sources["duplicate_candidate_groups"] == len(groups)

    verified = 0
    for group in groups:
        digest = group["sha256"]
        assert len(digest) == 64, group
        assert group["work"] and group["design"], \
            "a duplicate candidate must be the same bytes on both sides: " + digest[:12]
        for side, root in (("work", WORK_SOURCE), ("design", DESIGN_SOURCE)):
            for entry in group[side]:
                prefix, _, relative = entry.partition(":")
                assert prefix in {"WORK-LAB", "DESIGN-LAB"}, entry
                path = root / relative
                assert path.is_file(), entry
                assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, entry
                verified += 1
    assert verified >= 2 * len(groups), (verified, len(groups))

    rows = [line for line in (TARGET_ROOT / "migration" / "deferred-register.md")
            .read_text(encoding="utf-8").splitlines() if line.startswith("| D-")]
    assert len(rows) >= 13, len(rows)
    for line in rows:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert len(cells) == 10, cells
        identifier, kept, gap, priority = cells[0], cells[3], cells[4], cells[5]
        assert identifier.startswith("D-"), cells
        assert kept and kept not in {"—", "-"}, ("延期必须写明保留的实现/合同/入口", cells)
        assert gap and priority, ("延期必须有差距与分期", cells)
    excluded = [line for line in rows if "排除" in line]
    assert excluded, "the owner's explicit exclusions must be recorded as exclusions"
    for line in excluded:
        assert "手机" in line or "字库" in line or "素材" in line or "企业" in line, line


def test_host_bridge_script_is_reachable_where_the_adapter_probes():
    """F06 packaging gap, closed on the packaged path rather than by moving code."""
    from design_lab.adapters import photoshop_com
    assert photoshop_com._bridge() == BRIDGE_PACKAGED.read_bytes()
    assert BRIDGE_PACKAGED.read_bytes() == BRIDGE_SOURCE_OF_TRUTH.read_bytes(), \
        "the packaged copy has drifted from the source of truth"


def test_control_plane_parses_yaml_now_that_the_dependency_is_present():
    """The one real import the project venv lacked, and the behaviour it gated."""
    from domains.work.control import control_service
    resolved, state = control_service._field_presence("adapter:\n  verb: save\n", "adapter.verb")
    assert state == "KEY_PATH_RESOLVES" and resolved is True, (resolved, state)
    missing, state_missing = control_service._field_presence("adapter:\n  other: 1\n",
                                                            "adapter.verb")
    assert state_missing == "KEY_PATH_RESOLVES" and missing is False, (missing, state_missing)
    not_mapping, state_bad = control_service._field_presence("- a\n- b\n", "adapter.verb")
    assert (not_mapping, state_bad) == (None, "DOCUMENT_NOT_A_MAPPING")
    absent, state_absent = control_service._field_presence(None, "adapter.verb")
    assert (absent, state_absent) == (None, "FILE_ABSENT")


#: pip subcommands that can reach an index, and therefore must be pinned offline.
PIP_NETWORK_SUBCOMMANDS = {"wheel", "install", "download", "index", "search"}
#: pip invocations that are read-only by construction. Listed explicitly so the
#: test does not quietly widen "every pip line" to lines that cannot carry the
#: switches (``pip config list`` is recorded without ``--isolated`` on purpose —
#: ``--isolated`` is what suppresses the config it is there to read).
PIP_READ_ONLY_SUBCOMMANDS = {"config", "--version"}


def _pip_subcommand(command: list[str]) -> str:
    after = command[command.index("pip") + 1:]
    for token in after:
        if not token.startswith("-"):
            return token
        if token == "--version":
            return token
    return ""


def test_local_dependency_step_is_recorded_and_reversible():
    """The environment change is evidence, not an undocumented mutation.

    What this JSON says about the network is a self-report — the same operation
    wrote it — so the claim is checked against things the record cannot assert
    its way into: the source must be a real local path, no field may name a
    scheme, and the files it claims to have placed must be where it says. The
    pip half of the offline story is checked separately, from command lines.
    """
    document = json.loads((TARGET_ROOT / ".project-local/audit/20261030-qoder-ed9037"
                           / "local-dependency-step.json").read_text(encoding="utf-8"))
    assert document["network_used"] is False
    assert document["source_version"] == "PyYAML 6.0.3"
    assert document["import_probe"]["exit_code"] == 0
    assert document["deliberately_removed_binaries"], "the cp312 extension must not ship"
    # independent of that self-report: no URL, and the "source" really is a path
    blob = json.dumps(document, ensure_ascii=False)
    assert "http://" not in blob and "https://" not in blob and "pip install" not in blob
    source = Path(document["source"])
    assert source.is_dir(), "the claimed offline cache source does not exist locally"
    assert source.is_absolute() and not source.drive.startswith(("E:", "F:"))
    destination = Path(document["destination"])
    assert destination.is_dir(), destination
    for distribution, files in document["packages_added"].items():
        placed = destination / distribution
        assert placed.is_dir(), distribution
        for name in files:
            assert (placed / name).is_file(), (distribution, name)
    for removed in document["deliberately_removed_binaries"]:
        assert not (destination / removed).exists(), removed
    rollback = (TARGET_ROOT / ".project-local/audit/20261030-qoder-ed9037"
                / "rollback-local-dependency-step.ps1")
    assert rollback.is_file()
    text = rollback.read_text(encoding="utf-8")
    assert text.count("Remove-Item") == 2 and "yaml" in text, text


def test_offline_install_pip_command_lines_are_actually_offline():
    """``network_used: false`` is not evidence; the pip argv is.

    Every recorded pip line is re-read from the build reports and checked for the
    two switches that make an index unreachable. A line that runs a
    network-capable subcommand without them, or a network-capable subcommand that
    is not in the declared set, fails here even if the report's own summary says
    the run was offline.
    """
    import importlib.util

    reports = sorted((TARGET_ROOT / ".project-local" / "build").glob("*/build-report.json"))
    assert reports, ("no offline build report on this machine: .project-local is not in "
                     "Git, so this claim can only be re-checked where the build ran")
    spec = importlib.util.spec_from_file_location(
        "offline_install_under_test", TARGET_ROOT / "scripts" / "build_offline_install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert "--isolated" in module.PIP_GLOBAL, module.PIP_GLOBAL
    assert module.PIP_OFFLINE == ["--no-index"], module.PIP_OFFLINE

    seen = 0
    for report in reports:
        document = json.loads(report.read_text(encoding="utf-8"))
        steps = document.get("steps") or []
        assert steps, report
        for step in steps:
            command = step["command"]
            if "pip" not in command:
                continue
            seen += 1
            subcommand = _pip_subcommand(command)
            assert subcommand in (PIP_NETWORK_SUBCOMMANDS | PIP_READ_ONLY_SUBCOMMANDS), \
                (report, command)
            if subcommand in PIP_NETWORK_SUBCOMMANDS:
                assert "--no-index" in command, (report, command)
                assert "--isolated" in command, (report, command)
                assert "--no-deps" in command, (report, command)
                assert "download" not in command, (report, command)
            else:
                assert subcommand in PIP_READ_ONLY_SUBCOMMANDS, (report, command)
    assert seen >= len(reports), (seen, len(reports))
    # the report's own offline summary must agree with the argv it recorded
    for report in reports:
        document = json.loads(report.read_text(encoding="utf-8"))
        if "network_used" in document:
            assert document["network_used"] is False, document["network_used"]


def test_pre_push_guard_is_present_and_blocking():
    """A00「不推送不发布」has to be an assertion that can fail, not a sentence in a doc.

    The hook is a mistype-guard, not network isolation. The first-upload round the owner
    authorised moved it out and back by digest without using ``--no-verify``, so this pins
    the three facts that make that exception auditable: the guard is still there, still
    wired at the default path, and still refuses when actually invoked — locally, with a
    dummy ref line on stdin, never a real push.
    """
    import shutil

    hook = TARGET_ROOT / ".git" / "hooks" / "pre-push"
    assert hook.is_file(), "pre-push guard is gone; the mistype-guard was supposed to survive"
    body = hook.read_text(encoding="utf-8", errors="replace")
    assert body.startswith("#!"), body[:40]
    assert "exit 1" in body, body[:200]

    moved = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=str(TARGET_ROOT),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert moved.stdout.strip() == "", ("core.hooksPath points away from .git/hooks: "
                                        + moved.stdout)

    shell = shutil.which("sh") or shutil.which("bash")
    assert shell, "no POSIX shell available to invoke the hook locally"
    probe = subprocess.run([shell, str(hook), "origin", "git@example.invalid:nowhere.git"],
                           input="refs/heads/probe " + "0" * 40 + " refs/heads/probe "
                                + "1" * 40 + "\n",
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           cwd=str(TARGET_ROOT), timeout=120)
    assert probe.returncode != 0, "the guard let a push through: " + probe.stdout
    assert "blocked" in (probe.stderr + probe.stdout).lower(), probe.stderr


def test_every_adobe_host_bridge_is_packaged_and_byte_identical():
    """Each adapter probes ``design_lab/resources/adobe/<name>`` FIRST, so that copy is
    the product surface — and it must be the source repository's own bytes, not a
    hand-copied look-alike.

    This started as a Photoshop-only guard. The Illustrator bridge was absent from the
    packaged layout and from the migration rules, which made ILLUSTRATOR_BRIDGE_MISSING
    reachable for the wrong reason; both are now declared in ``FILE_COPIES``, so the pair
    is asserted together to keep the second one from drifting back out.
    """
    cases = [
        ("photoshop",
         TARGET_ROOT / "domains/design/design_lab/resources/adobe/photoshop-native-assemble.jsx",
         DESIGN_SOURCE / "integrations/hosts/adobe/photoshop-reconstruction/legacy-assemble.jsx"),
        ("illustrator",
         TARGET_ROOT / "domains/design/design_lab/resources/adobe/reconstruction-assemble.jsx",
         DESIGN_SOURCE / "integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx"),
    ]
    for label, packaged, truth in cases:
        assert packaged.is_file(), label + " bridge is not packaged where the adapter probes"
        assert packaged.read_bytes() == truth.read_bytes(), (
            label + " bridge drifted from the source repository's bytes")

    # the adapters must resolve exactly their own packaged path, in source layout
    sys.path.insert(0, str(TARGET_ROOT / "domains" / "design"))
    try:
        from design_lab.adapters import illustrator_com, photoshop_com
    except ImportError as exc:  # pragma: no cover - install layout is asserted elsewhere
        pytest.fail("adapters unimportable in this layout: " + str(exc))
    assert b"illustrator" in illustrator_com._bridge().lower()
    assert photoshop_com is not None


def test_no_register_carries_a_doubled_line_ending():
    """``write_text`` without ``newline=""`` translates every \\n into \\r\\n, so a CSV that
    already ended rows with \\r\\n comes out as \\r\\r\\n: one phantom empty row per record.

    DictReader skips empty rows silently, so row counts, status histograms and every
    downstream test stayed green while two shipped registers were byte-malformed. This
    guard reads raw bytes because no text-mode reader can see the defect.
    """
    offenders = {}
    for path in sorted((TARGET_ROOT / "migration").rglob("*.csv")):
        blob = path.read_bytes()
        doubled = blob.count(b"\r\r\n")
        if doubled:
            offenders[path.name] = doubled
    assert offenders == {}, ("registers with doubled line endings (phantom empty rows): "
                             + str(offenders))


def test_coverage_row_identity_is_the_pair_and_the_extra_rows_are_the_fan_out():
    """Row count > path count is a property of the register, not a miscount.

    DESIGN emits more rows than it has source files because some files were copied to more
    than one destination and each destination is judged on its own. Nothing checked that:
    a reader comparing the register against the source inventory saw two different numbers
    and no reason, and a genuine accidental duplicate would have hidden inside the same
    difference. So the pair is pinned as the row key, the surplus is recomputed from the
    register's own per-path destination sets (no count is quoted in this docstring -- a
    remembered number here went stale the moment a real migration added one destination),
    no register row may invent a destination the
    copy manifest does not record, and every named destination must be a file in this tree.

    The last half of this test is the two-reading gap the 2026-10-31 sweep found: the copy
    engine walks directories while the registers use ``git ls-files``. The files that exist
    only in the walk are ones the *source repository itself* ignores -- 253 node_modules
    entries and DESIGN-LAB's ``.verify-chain-ok`` pass marker, whose content is ``ok <sha>``
    for a commit of that other repository. That marker had been copied into the tracked
    tree, where it reads as evidence for a verification chain this project never ran; it is
    now excluded by ``SOURCE_IGNORED_NAMES`` and removed, and this test holds both halves
    shut: the walk cannot re-copy it, and the manifest cannot still claim it.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "migrate_sources_under_coverage_test", TARGET_ROOT / "scripts" / "migrate_sources.py")
    migrator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migrator)
    assert migrator._skipped(("design-lab", "config", ".verify-chain-ok"))
    assert migrator._skipped(("apps", "workbench", "node_modules", ".bin", "playwright"))
    assert not migrator._skipped(("design-lab", "config", "task-ledger-r3.json"))

    root_text = str(TARGET_ROOT).replace("\\", "/") + "/"
    manifest_targets = {record["target"].replace("\\", "/").removeprefix(root_text)
                        for group in json.loads((TARGET_ROOT / "migration" / "copies.json")
                                                .read_text(encoding="utf-8-sig"))["copies"]
                        for record in group["records"]}
    # A destination may also be justified by the migrator's declared single-file copy table --
    # but only when the bytes are re-hashed here and agree. Recomputed independently of
    # build_source_coverage so the register cannot define "copied" for itself.
    for repo_root, src_rel, dst_rel in (list(migrator.FILE_COPIES)
                                         + list(migrator.AUTOMATION_PACKED_FILES)):
        source, destination = Path(repo_root) / src_rel, TARGET_ROOT / dst_rel
        if source.is_file() and destination.is_file() and \
           hashlib.sha256(source.read_bytes()).hexdigest() == \
           hashlib.sha256(destination.read_bytes()).hexdigest():
            manifest_targets.add(dst_rel.replace("\\", "/"))
    for label in ("work", "design"):
        path = TARGET_ROOT / "migration" / ("source-coverage-%s.csv" % label)
        rows = list(csv.DictReader(io.StringIO(path.read_bytes().decode("utf-8-sig"),
                                               newline="")))
        pairs = [(row["path"], row["target"]) for row in rows]
        assert len(pairs) == len(set(pairs)), (
            label + "：同一个 (来源, 去向) 出现多次 —— 那才是真正的重复行")
        per_path = collections.Counter(row["path"] for row in rows)
        surplus = sum(count - 1 for count in per_path.values())
        destinations = collections.defaultdict(set)
        for row in rows:
            if row["target"]:
                destinations[row["path"]].add(row["target"])
        assert surplus == sum(len(set(targets)) - 1 for targets in destinations.values()), (
            label + "：多出来的行数不等于「一来源多去向」的扇出，说明有行不是去向而是重复")
        invented = sorted(row["target"] for row in rows
                          if row["target"] and row["target"].replace("\\", "/")
                          not in manifest_targets)
        assert invented == [], (label + "：登记了复制清单里没有的去向：" + str(invented[:5]))
        absent = sorted({row["target"] for row in rows if row["target"]
                         and not (TARGET_ROOT / row["target"]).is_file()})
        assert absent == [], ("登记说已经落地的去向在树上不存在：" + str(absent[:5]))

    marker = (TARGET_ROOT / "domains" / "design" / "design_lab" / "resources" / "repo"
              / "design-lab" / "config" / ".verify-chain-ok")
    assert not marker.exists(), "来源仓自己忽略的通过标记不应留在候选里"
    assert not any(".verify-chain-ok" in target for target in manifest_targets), \
        "复制清单不应再记录一个已被排除的去向"



def test_the_tracked_coverage_registers_are_not_stale():
    """The published per-file registers must equal what the builder produces right now.

    Their ``authority`` column stores ``file:line`` for text searched inside this document and
    inside ``build_f01_disposition.py``. Every 42 rows that cite ``docs/CODEX-AUDIT-ENTRY.md``
    point at one line today; a single inserted line above it would move all 42 citations onto
    unrelated prose, and the existing guard -- "the cited line number is in range and the file
    exists" -- would stay green. ``--check`` closes that by comparing the rebuilt rows with the
    tracked ones, in memory, so verification is still not a writer.
    """
    check = subprocess.run([sys.executable, "-B", "-X", "utf8",
                            str(TARGET_ROOT / "scripts" / "build_source_coverage.py"), "--check"],
                           cwd=str(TARGET_ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800)
    assert check.returncode == 0, (
        "覆盖登记比它引用的文本旧了；重跑 scripts/build_source_coverage.py 再重跑下游登记表。"
        + check.stdout[-600:] + check.stderr[-600:])
