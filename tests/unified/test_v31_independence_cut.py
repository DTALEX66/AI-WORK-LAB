# SPDX-License-Identifier: MIT
"""V31: the cut from the two source repositories is one switch, and its refusals stay distinct.

Owner's criterion, verbatim: 「设三个环境变量指向不存在的路径，全仓即进入"来源已删除"态，不需要
改任何一个字节」 -- and every gate must then answer with a conclusion that can be told apart from
the others. Three classes, which must not collapse into one another:

  (a) the source root is not on this machine: by design. The register names it and stops.
  (b) the clone carries no local working state and no configured remote: a prerequisite of the
      machine that wrote the record, not a defect of the repository.
  (c) the register genuinely drifted: a defect, and the only class that returns 1.

The 2026-11-02 attempt reached its conclusion by rewriting six files inside the clone, so it
measured a switch a reviewer does not have; and because one spelling of the root was left
untouched, the generator that should have answered ``SOURCE_REPO_ABSENT`` found the real
neighbour and published ``drifted`` instead. Every node here is driven by the environment or by a
plant, and each names the refusal it expects.

Two things this file deliberately does not contain, because ``test_v23`` classifies a test file as
machine-bound on them and the guards below are the ones that must keep running in a bare clone: a
virtualenv interpreter path, and either forbidden spelling of a source root (the planted texts are
assembled from fragments for that reason).
"""
from __future__ import annotations

import contextlib
import csv
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TARGET_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = TARGET_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import source_roots  # noqa: E402

#: A path with nothing at it. Named so that neither the resolver's defaults nor the spelling
#: guard can mistake it for one of the three real roots.
GONE = str(TARGET_ROOT.parent / "awl-cut-no-source-root-here")
SWITCH = {source_roots.ENVIRONMENT["work"]: GONE,
          source_roots.ENVIRONMENT["design"]: GONE + "-design",
          source_roots.ENVIRONMENT["archive"]: GONE + "-archive"}
#: The consumers' own attribute names, in fragments: two of them are literally one of
#: ``test_v23.PREREQ``'s machine prerequisites.
ATTR_WORK = "WORK_SOURCE" + "_ROOT"
ATTR_DESIGN = "DESIGN_SOURCE" + "_ROOT"
#: The two forbidden spellings, assembled so this file does not carry the pattern it plants.
WORD_WORK = "WORK" + "-LAB"
WORD_ARCHIVE = "Project" + " Archiving"
MACHINE = "All " + "projects"


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name + "_v31", SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _v23():
    """The clone-reproducibility module, loaded under a name pytest will not collect."""
    spec = importlib.util.spec_from_file_location(
        "v23_helpers", TARGET_ROOT / "tests" / "unified" / "test_v23_clone_repro.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(script: str, argv: list[str], env_extra: dict | None = None,
         timeout: int = 3600) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, "-B", "-X", "utf8", str(SCRIPTS / (script + ".py")),
                           *argv], cwd=str(TARGET_ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=timeout)


def _payload(completed: subprocess.CompletedProcess) -> dict:
    lines = (completed.stdout or "").strip().splitlines()
    assert lines, "the gate printed nothing on stdout: " + (completed.stderr or "")[-600:]
    return json.loads(lines[-1])


def test_absent_roots_refuse_by_name_and_publish_no_drift_field():
    """(a): with the switch set, the coverage builder answers rc=3 and has no drift reading.

    The wrong-typed refusal is the defect pinned here. The previous cut run answered a missing
    source with ``drifted`` plus ``rows_changed`` work 90 / design 1607, which reads as a broken
    register and sends the next agent off to "repair" rows that never moved.
    """
    completed = _run("build_source_coverage", ["--check"], SWITCH)
    payload = _payload(completed)
    assert completed.returncode == 3, (completed.returncode, payload)
    assert payload["error"] == "SOURCE_REPO_ABSENT", payload
    assert payload["verdict"] == "NOT_RECOMPUTABLE_HERE", payload
    assert "drifted" not in payload and "rows_changed" not in payload, (
        "the absence path also published a drift reading, so the two classes are not separable: "
        "%s" % payload)
    assert {entry["label"] for entry in payload["absent"]} == {"work", "design"}, payload


def test_a_moved_register_is_drift_and_is_not_excused_by_absence(tmp_path):
    """(c): the other path through the same gate -- readable roots, one published row is wrong.

    ``--check`` is pointed at copies of the two registers with one value planted in each. Absence
    and drift must be exclusive, so this asserts the half the previous node cannot: a
    ``drifted`` population and no ``error`` field. It needs the read-only sources and says so by
    name when this machine does not have them.
    """
    missing = source_roots.absent_roots()
    if missing:
        pytest.skip("this node re-verifies the registers against the read-only sources, and the "
                    "switch says they are absent: %s" % [entry["root"] for entry in missing])
    for label in ("work", "design"):
        original = TARGET_ROOT / "migration" / ("source-coverage-" + label + ".csv")
        with original.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = list(reader.fieldnames or [])
            rows = [dict(row) for row in reader]
        assert rows, original
        rows[0]["registered"] = "PLANTED_BY_V31"
        with (tmp_path / original.name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    module = _module("build_source_coverage")
    module.OUT_DIR = tmp_path
    module.WORK = source_roots.work_root()
    module.DESIGN = source_roots.design_root()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = module.main(["--check"])
    payload = json.loads(buffer.getvalue())     # parse the whole document, not its last line
    assert rc == 1, (rc, payload)
    assert payload["drifted"], payload
    assert "error" not in payload, "a real drift was reported as an absence: %s" % payload


def test_the_switch_reaches_every_script_that_resolves_a_root():
    """One variable per root, and all seven consumers agree with it after a fresh import.

    Each module snapshots its root into a module-level attribute -- that is what the existing
    monkeypatch targets rely on -- so the only way to show nobody was missed is to set the
    variables, re-import each file from disk, and read the attribute back. A half-wired consumer
    keeps the old path and reports a green measured on somebody else's machine, which is exactly
    how the previous round ended up with edited files instead of a switch.
    """
    driver = """
import importlib.util, json, sys
from pathlib import Path
scripts = Path(sys.argv[1])
plan = json.loads(sys.argv[2])
sys.path.insert(0, str(scripts))
import source_roots as sr
expected = {side: str(sr.resolve(side)) for side in ("work", "design", "archive")}
values = {}
for name, pairs in plan.items():
    spec = importlib.util.spec_from_file_location(name + "_driver", scripts / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except BaseException as exc:
        values[name + ".__import__"] = "IMPORT-FAILED %s: %s" % (type(exc).__name__, str(exc)[:160])
        continue
    for attribute, side in pairs:
        values[name + "." + attribute] = str(getattr(module, attribute, "<MISSING ATTRIBUTE>"))
print(json.dumps({"values": values, "expected": expected}))
"""
    plan = {"migrate_sources": [[ATTR_WORK, "work"], [ATTR_DESIGN, "design"]],
            "build_migration_map": [[ATTR_WORK, "work"], [ATTR_DESIGN, "design"]],
            "migrate_work_modules": [[ATTR_WORK, "work"]],
            "build_f01_disposition": [["WORK_ROOT", "work"], ["DESIGN_ROOT", "design"]],
            "build_source_coverage": [["WORK", "work"], ["DESIGN", "design"],
                                      ["UNIFIED_ARCHIVE_ROOT", "archive"]]}
    completed = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", driver,
                                str(SCRIPTS), json.dumps(plan)],
                               cwd=str(TARGET_ROOT), capture_output=True,
                               text=True, encoding="utf-8", errors="replace",
                               env={**os.environ, **SWITCH}, timeout=900)
    assert completed.returncode == 0, completed.stderr[-800:]
    answer = json.loads(completed.stdout.strip().splitlines()[-1])
    expected_total = sum(len(pairs) for pairs in plan.values())
    assert len(answer["values"]) == expected_total, (
        "the driver read %d attributes, the plan declares %d -- a consumer was skipped, which is "
        "how a half-rewired repository looks green: %s"
        % (len(answer["values"]), expected_total, sorted(answer["values"])))
    wrong = {key: value for key, value in answer["values"].items()
             if not value.startswith("IMPORT-FAILED")
             and value != answer["expected"][dict((a, s) for pairs in plan.values()
                                                  for a, s in pairs)[key.split(".", 1)[1]]]}
    assert not wrong, (
        "these consumers kept a root of their own, so the switch does not reach them: %s (switch: %s)"
        % (wrong, SWITCH))


def test_the_two_consumers_that_resolve_at_call_time_also_follow_the_switch():
    """``build_audit_state`` snapshots at import; ``migrate_business_data`` asks on every call.

    Both must follow the switch, and neither may be assumed from the other. The second is the
    interesting one: its answer is about a *candidate* path, so a deleted source root has to stop
    protecting paths under it while a real one still does -- otherwise the same string is
    protected here and writable there.
    """
    for name, value in SWITCH.items():
        os.environ[name] = value
    try:
        state = _module("build_audit_state")
        assert str(state.SOURCES["work"]) == SWITCH[source_roots.ENVIRONMENT["work"]], state.SOURCES
        assert str(state.SOURCES["design"]) == SWITCH[source_roots.ENVIRONMENT["design"]]
        business = _module("migrate_business_data")
        assert str(business.source_roots.work_root()) == SWITCH[source_roots.ENVIRONMENT["work"]]
        outside = business.protected_reason(Path(GONE) / "services")
        assert outside is None, (
            "with the source root switched away, a path under the switched name is still called "
            "protected, so the policy resolved something other than the switch: %s" % outside)
    finally:
        for name in SWITCH:
            os.environ.pop(name, None)
    real = source_roots.work_root()
    if real.is_dir():
        guarded = _module("migrate_business_data").protected_reason(real / "services")
        assert guarded and "source repository" in guarded, (
            "the real source root exists and its working tree is not protected: %r" % guarded)


def test_the_migrate_plan_refuses_for_the_root_not_for_its_own_numbering():
    """(a) one gate later: ``--plan`` must not answer rc=0 with a count it could not compute.

    Measured on the 2026-11-02 cut run: with both roots switched away, ``intended_set`` had
    nothing to enumerate, so 1,092 destination files looked unowned while the gate still returned
    0. The repository's own rule for this gate is 「unmanaged 必须为 0」, so a quiet 0 under a
    number nobody could compute is the worst answer available.
    """
    completed = _run("migrate_sources", ["--plan"], SWITCH, timeout=900)
    payload = _payload(completed)
    assert completed.returncode == 3, (completed.returncode, payload)
    assert payload["error"] == "SOURCE_REPO_ABSENT", payload
    assert payload["verdict"] == "NOT_RECOMPUTABLE_HERE", payload
    assert {entry["label"] for entry in payload["absent"]} == {"work", "design"}, payload
    assert "could not enumerate" in payload["note"], payload
    control = _run("migrate_sources", ["--plan"], timeout=900)
    control_payload = _payload(control)
    if control_payload.get("error") == "SOURCE_REPO_ABSENT":
        assert control.returncode == 3, control_payload
    else:
        assert control.returncode in (0, 1), (control.returncode, control_payload)
        assert "error" not in control_payload, control_payload


def test_the_audit_state_classes_absence_prerequisite_and_drift_apart():
    """(a)/(b)/(c) inside one generator: three lists, and a plant in any of them moves the verdict.

    ``source_repos`` is where a missing root and a stale digest used to look identical;
    ``upload_facts`` is where a clone's absent hook used to be charged to the repository.
    ``pushed_branch`` is deliberately outside the machine-local set: it is a claim about the
    project, so writing it as a false value has to be drift.
    """
    module = _module("build_audit_state")
    tracked = json.loads((TARGET_ROOT / "docs" / "AUDIT-STATE.json").read_text(encoding="utf-8"))

    def classes(mutate):
        rebuilt = json.loads(json.dumps(tracked))
        mutate(rebuilt)
        return module._section_classes(tracked, rebuilt)

    def untouched(_rebuilt):
        return None

    assert classes(untouched) == ([], [], []), "an untouched record already disagrees with itself"

    def absent(rebuilt):
        for name, entry in rebuilt["source_repos"].items():
            entry["root"] = GONE
            entry["head_observed"] = module.SOURCE_ROOT_ABSENT
            entry[module.SOURCE_NOT_OBSERVED_KEY] = {"repository": name, "root_absent": GONE,
                                                    "reason": "planted"}

    assert classes(absent) == ([], ["source_repos"], []), classes(absent)

    def absence_plus_a_planted_row_count(rebuilt):
        absent(rebuilt)
        rebuilt["registers"]["migration/task-acceptance.csv"]["rows"] += 1

    drift, unobservable, _prereq = classes(absence_plus_a_planted_row_count)
    assert drift == ["registers"], (
        "the absence excused a planted row count -- that is the collapse the whole file exists "
        "to prevent: %s" % ((drift, unobservable),))
    assert unobservable == ["source_repos"], (drift, unobservable)

    def one_field_outside_absence(rebuilt):
        absent(rebuilt)
        rebuilt["source_repos"]["work"]["remote_url"] = "planted"

    drift, unobservable, _p = classes(one_field_outside_absence)
    assert drift == ["source_repos"], (drift, unobservable)

    def hook_only(rebuilt):
        rebuilt["upload_facts"]["prepush_hook"] = {"path": ".git/hooks/pre-push", "present": False,
                                                   "sha256_observed": None, "bytes": 0,
                                                   "blocks_push_when_invoked": False}

    assert classes(hook_only) == ([], [], ["upload_facts"]), classes(hook_only)

    def branch_false(rebuilt):
        rebuilt["upload_facts"]["pushed_branch"] = None

    drift, _u, prereq = classes(branch_false)
    assert drift == ["upload_facts"], (
        "pushed_branch was written as a false value and the machine-prerequisite class excused "
        "it: drift=%s prereq=%s" % (drift, prereq))


def test_the_spelling_guard_refuses_a_planted_file(tmp_path):
    """The guard's own population, proven: it enumerates, it can be pointed at a plant, and the
    real tree is clean.

    A guard that enumerates nothing keeps any claim green, and the exemption list has to stay
    narrow -- only the resolver and this file itself are allowed past it.
    """
    v23 = _v23()
    planted = tmp_path / "scripts"
    nested = tmp_path / "tests" / "unified"
    planted.mkdir()
    nested.mkdir(parents=True)
    (planted / "second_spelling.py").write_text(
        'WORK = Path(r"D:\\%s\\%s")\n' % (MACHINE, WORD_WORK), encoding="utf-8")
    (nested / "third_spelling.py").write_text(
        'ARCHIVE = TARGET_ROOT.parent / "%s"\n' % WORD_ARCHIVE, encoding="utf-8")
    (tmp_path / "docs" / "history").mkdir(parents=True)
    (tmp_path / "docs" / "history" / "inert.py").write_text(
        'p = r"D:\\%s\\%s"\n' % (MACHINE, WORD_WORK), encoding="utf-8")
    found = {p.relative_to(tmp_path).as_posix() for p in v23._active_python_files(tmp_path)}
    assert found == {"scripts/second_spelling.py", "tests/unified/third_spelling.py"}, (
        "the enumeration skipped the planted file or reached into the inert history area: %s"
        % sorted(found))
    offenders = {}
    for path in v23._active_python_files(tmp_path):
        text = path.read_text(encoding="utf-8")
        hits = sorted({m.group(0) for pattern in v23.FORBIDDEN_ROOT_SPELLINGS
                       for m in pattern.finditer(text)})
        if hits:
            offenders[path.relative_to(tmp_path).as_posix()] = hits
    assert set(offenders) == found, offenders
    real = [path.relative_to(TARGET_ROOT).as_posix()
            for path in v23._active_python_files(TARGET_ROOT)
            if any(pattern.search(path.read_text(encoding="utf-8", errors="replace"))
                   for pattern in v23.FORBIDDEN_ROOT_SPELLINGS)]
    assert not real, "活跃代码里又出现了第二种根拼写，环境变量开关到不了这些文件：%s" % sorted(real)


def test_history_bytes_that_no_ledger_names_are_refused():
    """#58: the exemption cannot grow into a blanket pass, and a new file is a finding.

    The population is enumerated from ``git ls-files`` in production, never from a ledger:
    starting from the ledger would only prove the ledger agrees with itself.
    """
    module = _module("check_project_current")
    tracked = ["docs/history/sources-20261101/a.md",
               "docs/history/sources-20261101/MANIFEST.csv",
               "docs/history/unclaimed/loose-note.md"]
    claims = {"docs/history/sources-20261101/a.md":
              "docs/history/sources-20261101/MANIFEST.csv:target_rel"}
    assert module.unclaimed_history_findings(tracked, claims) == [
        "HISTORY_BYTES_UNCLAIMED docs/history/unclaimed/loose-note.md"], (
        module.unclaimed_history_findings(tracked, claims))
    widened = module.unclaimed_history_findings(
        tracked, claims, exempt=tuple(list(module.HISTORY_SELF_CLAIM)
                                     + ["docs/history/unclaimed/loose-note.md"]))
    assert "HISTORY_CLAIM_EXEMPTION_NOT_A_LEDGER docs/history/unclaimed/loose-note.md" in widened, (
        "adding a name to the exemption list silenced it: an exemption that is not a ledger must "
        "be reported, or the guard decays into a list of allowances")
    assert module.unclaimed_history_findings(["docs/history/sources-20261101/a.md"],
                                            claims) == []
    real_tracked, errors = module.tracked_history_files()
    assert not errors, errors
    assert len(real_tracked) > 1000, (
        "the enumeration came back with almost nothing to check (%d) -- a guard over an empty "
        "population is not a guard" % len(real_tracked))
    assert module.unclaimed_history_findings(real_tracked, module.history_claims()) == []


def test_the_closure_probe_drives_the_switch_and_can_still_say_fail(tmp_path):
    """(b) for the sentinel after it moved: the probe names its answer, and refuses on demand.

    It used to scrape the sentinel out of one generator's text and hard-code a drive letter, so
    it proved one path on one machine. It now sets the override the way a reviewer would -- which
    means a tree without the resolver must produce a refusal, not a green.
    """
    audit = _module("audit_objective_closure")
    verdict = audit.probe_source_root_absent(TARGET_ROOT)
    assert verdict["status"] == "PASS", verdict
    assert verdict["sentinel_declared"] == source_roots.SOURCE_ROOT_ABSENT, verdict
    asked = Path(verdict["asked_about"])
    # the probe synthesises its absent path from the resolver's own default, so the pid inside it
    # belongs to the child process; assert what makes it a real absence instead of a literal
    assert not asked.exists(), verdict
    assert asked.parent == source_roots.DEFAULTS["work"].parent, verdict
    assert asked.name.startswith("awl-gone-"), verdict
    assert not verdict.get("refusals"), verdict
    (tmp_path / "scripts").mkdir()
    refused = _module("audit_objective_closure").probe_source_root_absent(tmp_path)
    assert refused["status"] != "PASS", (
        "the probe passed against a tree with no resolver, so its PASS measures nothing: %s"
        % refused)


def test_a_tree_without_the_receipt_refuses_by_name_and_still_sees_drift(tmp_path):
    """(b): no receipt on this machine is a named refusal, never a silent pass -- and never an excuse.

    The closure register's three receipt-derived columns cannot be reproduced in a clone, so the
    comparison exempts them. Exempting them and then answering 0 would make the gate read as a
    pass on a claim it did not check; and the opposite failure -- a missing receipt excusing a
    moved row -- is the collapse the rest of this file exists to prevent. Both directions are
    asserted by redirecting the module's own paths, so nothing in the tracked tree is touched.
    """
    with (TARGET_ROOT / "migration" / "audit-item-closure.csv").open(
            encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    assert rows, "the closure register is empty, so there is nothing to plant on"

    closure = _module("build_audit_item_closure")
    closure.RECEIPT = tmp_path / "absent-CLOSURE-STATE.json"       # a clone has no live receipt
    closure.archived_receipt_copy = lambda named: None             # ... nor the archived copy
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = closure.main([sys.argv[0], "--check"])
    payload = json.loads(buffer.getvalue())     # parse the whole document, not its last line
    assert rc == 3, (rc, payload)
    assert payload["receipt_present"] is False, payload
    assert payload["verdict"] == "NOT_OBSERVABLE_HERE", payload
    assert payload["register_drift"] is False, payload
    assert sorted(payload["receipt_columns_exempted"]) == sorted(closure.RECEIPT_COLUMNS), payload

    def drift_with_no_receipt():
        """Same machine state (no receipt), one published claim changed on the rebuild side.

        The plant goes into the builder's own row table rather than into a relocated register:
        retargeting ``TARGET_ROOT`` would move half a dozen other reads with it and the refusal
        would come from a tree that no clone ever looks like.
        """
        drifting = _module("build_audit_item_closure")
        drifting.RECEIPT = tmp_path / "absent-CLOSURE-STATE.json"
        drifting.archived_receipt_copy = lambda named: None
        identifier = sorted(drifting.ROWS)[0]
        drifted = dict(drifting.ROWS)
        drifted[identifier] = dict(drifting.ROWS[identifier])
        # plant in a column published verbatim: the evidence target is parsed by the resolver and
        # would raise instead of drifting, which would test the resolver rather than the comparison
        drifted[identifier]["unverified"] = (str(drifting.ROWS[identifier]["unverified"])
                                            + " PLANTED-BY-V31")
        drifting.ROWS = drifted
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = drifting.main([sys.argv[0], "--check"])
        return rc, json.loads(out.getvalue())

    rc, payload = drift_with_no_receipt()
    assert rc == 1, (rc, payload, "a moved claim was excused by the missing receipt")
    assert payload["register_drift"] is True, payload
    assert payload["verdict"] == "DRIFT", payload
    assert payload["receipt_present"] is False, payload


def test_the_isolated_install_verdict_names_the_report_it_could_not_read(tmp_path):
    """(b): the offline install ran where the wheel was built, and says so by name elsewhere.

    rc=2 is also what argparse uses for a usage error, which is why the closure audit reads the
    gate's own name before deciding whether a 2 was this caller's mistake. Both halves are pinned.
    """
    module = _module("build_isolated_install_verdict")
    module.BUILD_GLOB = str(tmp_path / "no-such-reports" / "*.json")
    errors = io.StringIO()
    out = io.StringIO()
    with contextlib.redirect_stderr(errors), contextlib.redirect_stdout(out):
        rc = module.main([sys.argv[0], "--check"])
    assert rc == 2, (rc, out.getvalue(), errors.getvalue())
    payload = json.loads(errors.getvalue().strip().splitlines()[-1])
    assert payload["error"] == "NO_ISOLATED_INSTALL_REPORT", payload
    assert "verify_isolated_install" in payload["hint"], payload
    audit = _module("audit_objective_closure")
    named = subprocess.CompletedProcess(args=[], returncode=2, stdout="",
                                       stderr=json.dumps(payload))
    assert audit.refusal_name(named) == "NO_ISOLATED_INSTALL_REPORT", audit.refusal_name(named)
    misuse = subprocess.CompletedProcess(args=[], returncode=2, stdout="",
                                        stderr="usage: build_x.py [--check]\nerror: unrecognized")
    assert audit.refusal_name(misuse) is None, (
        "an invoked-wrongly 2 was read as a designed absence, so INSTRUMENT_ERROR is unreachable")
