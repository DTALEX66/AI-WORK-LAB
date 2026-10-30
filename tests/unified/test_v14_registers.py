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
import hashlib
import json
import subprocess
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
    for label in ("work", "design"):
        rows = _read(TARGET_ROOT / ("migration/source-coverage-" + label + ".csv"))
        for row in rows:
            assert row["class"], row
            assert row.get("reason") or row["class"].startswith("COPIED_VERIFIED"), row
            if row["class"] in UNEXPLAINED:
                # SOURCE_UNREGISTERED is allowed only as a *named* population with an
                # owner decision outstanding; it must never hide inside another class
                assert row["class"] == "SOURCE_UNREGISTERED", row
                assert "owner" in row["reason"], row
        unregistered = [row["path"] for row in rows if row["class"] == "SOURCE_UNREGISTERED"]
        assert all(path.endswith(".py") for path in unregistered), unregistered[:5]


def test_coverage_gap_rows_match_the_f01_register(coverage):
    """The two registers must not disagree about the same file."""
    assert coverage["cross_check"]["registered_gap_python_paths_by_repo"]["work"] == 198
    assert coverage["cross_check"]["f01_register_reports_work_python_gaps"] == 198
    disposition = _read(TARGET_ROOT / "migration/work-gap-disposition.csv")
    assert len(disposition) == 198
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


def test_local_dependency_step_is_recorded_and_reversible():
    """The environment change is evidence, not an undocumented mutation."""
    document = json.loads((TARGET_ROOT / ".project-local/audit/20261030-qoder-ed9037"
                           / "local-dependency-step.json").read_text(encoding="utf-8"))
    assert document["network_used"] is False
    assert document["source_version"] == "PyYAML 6.0.3"
    assert document["import_probe"]["exit_code"] == 0
    assert document["deliberately_removed_binaries"], "the cp312 extension must not ship"
    rollback = (TARGET_ROOT / ".project-local/audit/20261030-qoder-ed9037"
                / "rollback-local-dependency-step.ps1")
    assert rollback.is_file()
    text = rollback.read_text(encoding="utf-8")
    assert text.count("Remove-Item") == 2 and "yaml" in text, text
