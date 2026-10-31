# SPDX-License-Identifier: MIT
"""V07: source migration is repeatable, and repeating it cannot undo the candidate.

The audited version of this file ran ``scripts/migrate_sources.py`` **in place** and
asserted only that record counts stayed the same. That was not idempotence — the
script deleted each destination tree with ``shutil.rmtree`` before re-copying, so
"same count" was guaranteed by the wipe, and any repair already present in the
target was silently reverted. The 2026-10-30 audit therefore recorded V07's PASS as
covering source copying only, with the caveat that "the script had already deleted
the original target tree at the moment of failure; there was no transactional
switch". The contract now is:

* the default invocation is a **read-only plan**; it writes nothing to the target;
* ``--apply`` is opt-in, needs ``--confirm REBUILD-MIGRATION``, writes file by file
  with write-then-move, and **never deletes**;
* a target whose managed files were repaired afterwards is **refused** rather than
  overwritten — the files listed in ``DECLARED_REWORK`` are exactly those repairs (the
  F01/F09 import and root repairs, later rounds' test repairs, this round's
  model-catalog projection fix), so refusing is the first thing this test checks.
  The count is deliberately not written here: it moves whenever a repair is declared,
  and a stale number in a docstring is a claim nothing checks.

What the old tests meant is preserved: reruns change no counts, the read-only
sources stay untouched (verified by digest, not by counting dirty files, as the
handoff required), and migrated digests still match their sources.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

TARGET_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = str(TARGET_ROOT / ".venv" / "Scripts" / "python.exe")
SCRIPT = TARGET_ROOT / "scripts" / "migrate_sources.py"
SOURCES = [TARGET_ROOT.parent / "WORK-LAB", TARGET_ROOT.parent / "DESIGN-LAB"]
SKIP_PARTS = {".mimosa", "__pycache__", ".pytest_cache"}


@pytest.fixture(scope="module")
def rehearsal(tmp_path_factory):
    """One isolated destination, populated once and shared by the apply tests.

    Module-scoped on purpose: a full apply writes ~1.4k files, and three separate
    rehearsals of the same tree would be three copies of the same bytes for no
    additional evidence. The first apply is what every later test compares against.
    """
    # Not tmp_path_factory: a pytest basetemp under a long run directory re-roots
    # the migrated tree past Windows' 260-character path limit (a packaged
    # domain-pack benchmark path is ~250 on its own), and the apply then fails for
    # the length, not for the code. The rehearsal only has to be outside the
    # candidate, so it goes somewhere short and is removed afterwards.
    root = Path(tempfile.gettempdir()) / ("awl-v07-%d" % os.getpid())
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    _run(["--apply", "--confirm", "REBUILD-MIGRATION", "--target-root", str(root)])
    try:
        yield root
    finally:
        # this tool's own rehearsal litter: ~1.4k files per run outside the
        # candidate, and no auditor asked to hash a temp tree
        shutil.rmtree(root, ignore_errors=True)


def _run(args, *, expect=0, cwd=TARGET_ROOT):
    completed = subprocess.run([VENV_PYTHON, "-B", "-X", "utf8", str(SCRIPT)] + list(args),
                               capture_output=True, text=True, cwd=str(cwd), timeout=1800,
                               encoding="utf-8", errors="replace")
    if expect is not None:
        assert completed.returncode == expect, (completed.returncode,
                                                completed.stdout[-1500:],
                                                completed.stderr[-3000:])
    return completed


def _source_state(root: Path) -> dict:
    listed = subprocess.check_output(["git", "ls-files", "--cached", "--others",
                                      "--exclude-standard", "-z"], cwd=str(root))
    state = {}
    for rel in sorted(set(x for x in listed.decode("utf-8").split("\0") if x)):
        if any(part in SKIP_PARTS for part in Path(rel).parts):
            continue
        path = root / rel
        state[rel] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "MISSING"
    return state


def _tree_state(root: Path) -> dict:
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file()}


#: The manifest this tool writes records the instant it ran, so it is the one
#: artifact of an apply that is *meant* to change every time. Comparing it by raw
#: hash would fail an idempotence test for a clock; its content is compared
#: separately, with the timestamp field dropped.
VOLATILE_MANIFEST = "migration/copies.json"
VOLATILE_KEYS = ("generated_at", "reviewed_at", "observed_at", "computed_at")


def _stable_state(root: Path) -> dict:
    state = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        if relative == VOLATILE_MANIFEST:
            document = json.loads(text)
            for key in VOLATILE_KEYS:
                document.pop(key, None)
            for group in document.get("copies", []):
                for record in group.get("records", []):
                    record.pop("target", None)  # absolute rehearsal path, not content
            text = json.dumps(document, ensure_ascii=False, sort_keys=True)
        state[relative] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return state


def test_plan_mode_writes_nothing_to_the_candidate():
    """The default run is an observation, not a rebuild."""
    before = _tree_state(TARGET_ROOT / "domains" / "work")
    manifest_before = (TARGET_ROOT / "migration" / "copies.json").read_bytes()
    completed = _run(["--plan"], expect=None)
    assert completed.returncode in (0, 1), completed.stderr[-1500:]
    report = json.loads(completed.stdout.strip().splitlines()[-1])
    assert report["target_root"] == str(TARGET_ROOT)
    assert "apply" not in report
    assert _tree_state(TARGET_ROOT / "domains" / "work") == before, \
        "a plan run must not change a single byte of the candidate"
    assert (TARGET_ROOT / "migration" / "copies.json").read_bytes() == manifest_before


def test_plan_reports_declared_rework_and_refuses_unexplained_rework():
    """The F01/F09 import and root repairs are exactly what a rerun used to erase.

    Every one of them is declared with attested bytes now, so the plan no longer has to
    shout about repairs it can see are intentional — and that is only honest if a NEW,
    undeclared edit still fails. The second half of this pair plants exactly that.
    """
    report_path = TARGET_ROOT / ".project-local" / "runs" / "v07-plan-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    completed = _run(["--plan", "--json-out", str(report_path)], expect=None)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    modified = {str(row["target"]).replace(chr(92), "/")
                for row in report["refusals"] if row["state"] == "MODIFIED"}
    assert modified, report["summary"]
    assert any("domains/work/control/sidecar.py" in path for path in modified), modified
    assert any("composition_root.py" in path for path in modified), modified
    rework = report["rework"]
    assert rework["modified_total"] == len(modified), (rework, modified)
    assert rework["declared_attested"] == rework["modified_total"], rework
    assert rework["unattested"] == [], rework
    assert completed.returncode == 0, (completed.returncode, completed.stdout[-800:])
    assert "unmanaged" in report
    # a declaration without a reason is decoration
    keys = _live_migration_module().DECLARED_REWORK
    for row in report["refusals"]:
        if row["state"] == "MODIFIED":
            assert row.get("rework_attested") is True, row
            assert row.get("rework_reason"), row
            # the label must be the declaration that names *this* destination, not any
            # other key that merely happens to be a suffix of it
            candidates = [name for name in keys if ("/" + row["target"]).endswith("/" + name)]
            assert candidates, row
            assert row["declared_rework"] == max(candidates, key=len), \
                {"row": row["declared_rework"], "candidates": candidates}


def _live_migration_module():
    """The migration script as it is on disk, imported once per process."""
    global _LIVE_MIGRATE
    if _LIVE_MIGRATE is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "migrate_sources_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LIVE_MIGRATE = module
    return _LIVE_MIGRATE


_LIVE_MIGRATE = None


def test_declaration_labels_the_most_specific_key(tmp_path):
    """A key can be a path suffix of a *different* destination, so first-match mislabels.

    ``design-lab/schemas/model-catalog-v1.schema.json`` is a suffix of
    ``domains/design/design_lab/resources/repo/design-lab/schemas/model-catalog-v1.schema.json``,
    and both are declared. The attestation (digest + size) happens to be the same for the
    three schema copies, so nothing fails when the shorter key wins the race -- the plan
    just reports a declaration that names another file, and which one wins depended on
    dict order. The planted mapping below puts the short key first on purpose: an
    implementation that returns the first suffix match labels the wrong file.
    """
    live = _live_migration_module()
    planted = {
        "schemas/model-catalog-v1.schema.json": ("x", 1, 1, "short key, listed first"),
        "repo/design-lab/schemas/model-catalog-v1.schema.json":
            ("y", 1, 1, "long key, listed second"),
    }
    deep = tmp_path / "domains/design/design_lab/resources/repo/design-lab/schemas"
    deep.mkdir(parents=True)
    handle = deep / "model-catalog-v1.schema.json"
    handle.write_bytes(b"")
    assert live._declared_rework_for(handle, planted) \
        == "repo/design-lab/schemas/model-catalog-v1.schema.json", \
        "first-match label: the plan would name the wrong destination"
    # the same call against the published mapping names the real, specific destination
    real = TARGET_ROOT / ("domains/design/design_lab/resources/repo/design-lab/schemas/"
                          "model-catalog-v1.schema.json")
    assert live._declared_rework_for(real) == \
        ("domains/design/design_lab/resources/repo/design-lab/schemas/"
         "model-catalog-v1.schema.json"), live._declared_rework_for(real)
    shallow = TARGET_ROOT / "design-lab/schemas/model-catalog-v1.schema.json"
    assert live._declared_rework_for(shallow) == "design-lab/schemas/model-catalog-v1.schema.json"


def test_undeclared_rework_still_fails_the_plan(rehearsal):
    """Falsification: corrupt one declared file in an applied rehearsal tree, where the
    engine wrote plain source bytes. The plan must call it unattested and exit non-zero."""
    target = rehearsal / "domains/work/control/sidecar.py"
    assert target.is_file(), sorted(str(p) for p in (rehearsal / "domains").rglob("*.py"))[:5]
    original = target.read_bytes()
    target.write_bytes(original + b"\n# planted undeclared edit\n")
    report_path = rehearsal / "drift-plan.json"
    try:
        completed = _run(["--plan", "--target-root", str(rehearsal),
                          "--json-out", str(report_path)], expect=None)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert completed.returncode == 1, (report.get("rework"), report.get("summary"),
                                           completed.stdout[-500:])
        assert report["rework"]["unattested"], report["rework"]
        assert any("sidecar.py" in path for path in report["rework"]["unattested"]), report
    finally:
        target.write_bytes(original)


def test_apply_without_confirmation_refuses_and_writes_nothing(tmp_path):
    rehearsal = tmp_path / "rehearsal"
    rehearsal.mkdir()
    completed = _run(["--apply", "--target-root", str(rehearsal)], expect=2)
    assert "APPLY_CONFIRMATION_REQUIRED" in completed.stderr
    assert _tree_state(rehearsal) == {}


def test_isolated_rehearsal_apply_is_idempotent(rehearsal, tmp_path):
    """The old acceptance meaning, kept: a rerun alters no bytes and no counts."""
    tree_first = _stable_state(rehearsal)
    assert tree_first, "the rehearsal wrote nothing"
    _run(["--apply", "--confirm", "REBUILD-MIGRATION", "--target-root", str(rehearsal),
          "--json-out", str(tmp_path / "apply-2.json")])
    assert _stable_state(rehearsal) == tree_first, "a rerun wrote different bytes"
    assert set(_tree_state(rehearsal)) == set(tree_first), "a rerun created or lost a file"
    second = json.loads((tmp_path / "apply-2.json").read_text(encoding="utf-8"))
    assert second["summary"].get("MODIFIED", 0) == 0
    assert second["summary"].get("would_write", 0) == 0, second["summary"]
    manifest = json.loads((rehearsal / "migration" / "copies.json").read_text(encoding="utf-8"))
    recorded = [row for group in manifest["copies"] for row in group["records"]]
    assert recorded, "the manifest carries no records"
    assert len({row["target"] for row in recorded}) == len(
        [row["target"] for row in recorded]), "the manifest accumulated duplicates on rerun"


def test_injected_interruption_leaves_previous_bytes_and_a_retry_completes(rehearsal, tmp_path):
    """Write-then-move must leave the prior bytes; the old script had already
    deleted the tree at the moment a copy failed."""
    settled = _stable_state(rehearsal)
    assert settled

    harness = tmp_path / "inject.py"
    harness.write_text(
        "import importlib.util as iu, os, pathlib, sys\n"
        "root = pathlib.Path(sys.argv[1]); rehearsal = pathlib.Path(sys.argv[2])\n"
        "spec = iu.spec_from_file_location('ms', str(root / 'scripts' / 'migrate_sources.py'))\n"
        "ms = iu.module_from_spec(spec); spec.loader.exec_module(ms)\n"
        "real = os.replace\n"
        "state = {'n': 0}\n"
        "def boom(src, dst):\n"
        "    state['n'] += 1\n"
        "    if state['n'] == 3:\n"
        "        raise OSError('INJECTED_RENAME_FAILURE')\n"
        "    return real(src, dst)\n"
        "ms.os.replace = boom\n"
        "plan = ms.build_plan(rehearsal)\n"
        "for row in plan['entries']:\n"
        "    if row['state'] == 'identical':\n"
        "        row['state'] = 'would_write'\n"
        "try:\n"
        "    ms.apply_plan(plan)\n"
        "    print('NO_FAILURE')\n"
        "except OSError as exc:\n"
        "    print('INJECTED', exc)\n"
        "print('LEFTOVER_TEMP', len([p for p in rehearsal.rglob('*.migrating')]))\n",
        encoding="utf-8")
    injected = subprocess.run([VENV_PYTHON, "-B", str(harness), str(TARGET_ROOT), str(rehearsal)],
                              capture_output=True, text=True, timeout=1800, encoding="utf-8",
                              errors="replace")
    assert "INJECTED" in injected.stdout, (injected.stdout[-800:], injected.stderr[-2000:])
    after_failure = _stable_state(rehearsal)
    assert set(after_failure) >= set(settled), sorted(set(settled) - set(after_failure))[:5]
    for rel, digest in settled.items():
        assert after_failure[rel] == digest, rel
    _run(["--apply", "--confirm", "REBUILD-MIGRATION", "--target-root", str(rehearsal)])
    assert _stable_state(rehearsal) == settled, "the retry did not restore the intended bytes"
    # and no stray temp survives the crash the harness injected
    assert not [path for path in rehearsal.rglob("*.migrating")]


def test_prune_reports_only_paths_this_tool_recorded(rehearsal, tmp_path):
    """Deletion is never performed here; it is named for a human to decide on."""
    before = _tree_state(rehearsal)
    _run(["--plan", "--prune", "--target-root", str(rehearsal),
          "--json-out", str(tmp_path / "prune.json")], expect=None)
    report = json.loads((tmp_path / "prune.json").read_text(encoding="utf-8"))
    assert "prune" in report, sorted(report)
    assert _tree_state(rehearsal) == before, "a prune report must not delete anything"


def test_sources_are_byte_identical_before_and_after_a_rerun():
    """Stronger than counting dirty files: the sources' own digests must not move."""
    before = {str(repo): _source_state(repo) for repo in SOURCES}
    _run(["--plan"], expect=None)
    for repo in SOURCES:
        after = _source_state(repo)
        assert before[str(repo)] == after, repo
        assert len(after) > 2000, "the source snapshot came back empty"


def test_migrated_file_digests_match_their_sources():
    manifest = json.loads((TARGET_ROOT / "migration" / "copies.json").read_text(encoding="utf-8"))
    # the patch set is read from the migration script, not only from the manifest: the
    # manifest is a snapshot of one applied run, so a newly declared patch would be skipped
    # by luck (a sampled file) or fail for the wrong reason.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "migrate_sources_live", TARGET_ROOT / "scripts" / "migrate_sources.py")
    live = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(live)
    patched = ({entry["file"] for entry in manifest["patches"]}
               | {rel for rel, _old, _new, _reason in live.PATCHES})
    declared = live.DECLARED_REWORK
    checked = 0
    attested = 0
    drifted = []
    absent = []
    for entry in manifest["copies"]:
        for record in entry["records"]:
            relative = str(record["target"]).replace(chr(92), "/")
            key = _live_migration_module()._declared_rework_for(TARGET_ROOT / relative)
            if key is not None:
                # rework here is declared, so the only acceptable state is "still exactly
                # the bytes the declaration attests"; anything else is unannounced drift
                digest, size, _delta, reason = declared[key]
                blob = Path(relative).read_bytes()
                assert hashlib.sha256(blob).hexdigest() == digest, (key, reason)
                assert len(blob) == size, (key, reason)
                attested += 1
                continue
            if any(relative.endswith(patched_file.replace(chr(92), "/"))
                   for patched_file in patched):
                continue  # patched on purpose after copy; digest recorded pre-patch
            target = Path(relative)
            if not target.is_file():
                absent.append(relative)
                continue
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if digest != record["sha256_target"]:
                drifted.append(relative)
            checked += 1
    # a full sweep, not a 25-file sample: the previous cap let a patched file pass simply
    # because the loop happened to break before reaching it
    assert absent == [], "copied targets vanished from the tree: " + str(absent[:10])
    assert drifted == [], "copied targets no longer match their recorded digest: " + str(drifted[:10])
    assert checked >= 1000, checked
    assert attested == len(declared), (attested, len(declared),
                                       "every declared rework must still be a copied target")


def test_mapping_rerun_is_idempotent():
    """The mapping artifacts must not drift. Two of them carry their own run
    timestamp, so those are compared with the timestamp field removed — asserting
    byte equality there would fail for a clock, not for a change of substance."""
    import csv
    builder = TARGET_ROOT / "scripts" / "build_migration_map.py"
    volatile = ("generated_at", "reviewed_at", "observed_at", "computed_at")

    def state() -> dict:
        out = {}
        for path in sorted((TARGET_ROOT / "migration").rglob("*")):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            try:
                document = json.loads(text)
            except ValueError:
                document = None
            if isinstance(document, dict):
                for key in volatile:
                    document.pop(key, None)
                text = json.dumps(document, ensure_ascii=False, sort_keys=True)
            out[path.relative_to(TARGET_ROOT).as_posix()] = hashlib.sha256(
                text.encode("utf-8")).hexdigest()
        return out

    def rows():
        with open(TARGET_ROOT / "migration" / "mapping.csv", encoding="utf-8-sig",
                  newline="") as handle:
            return list(csv.DictReader(handle))

    def raw() -> dict:
        out = {}
        for path in sorted((TARGET_ROOT / "migration").rglob("*")):
            if path.is_file():
                out[path.relative_to(TARGET_ROOT).as_posix()] = hashlib.sha256(
                    path.read_bytes()).hexdigest()
        return out

    before = state()
    before_raw = raw()
    before_rows = [(row["来源键"], row["处理方式"]) for row in rows()]
    subprocess.run([VENV_PYTHON, "-B", str(builder)], cwd=str(TARGET_ROOT), capture_output=True,
                   text=True, timeout=1800, check=True)
    first = rows()
    assert len(first) == 837
    subprocess.run([VENV_PYTHON, "-B", str(builder)], cwd=str(TARGET_ROOT), capture_output=True,
                   text=True, timeout=1800, check=True)
    second = rows()
    assert len(second) == 837
    assert [row["来源键"] for row in first] == [row["来源键"] for row in second]
    assert [row["处理方式"] for row in first] == [row["处理方式"] for row in second]
    assert state() == before, "regenerating the map changed substance, not just its clock"
    assert [(row["来源键"], row["处理方式"]) for row in rows()] == before_rows
    # byte level: a rerun must not even refresh a stamp, otherwise the candidate
    # manifest moves for a clock reading and an audit rerun looks like drift
    drifted = [name for name, value in raw().items() if before_raw.get(name) != value]
    assert drifted == [], "rerun rewrote these migration artefacts byte-wise: " + str(drifted)


def test_a_killed_migration_lands_the_same_bytes_as_a_clean_one():
    """L15「失败恢复」at the process level, for the source-copy tool itself.

    The rehearsal suite already injects an ``os.replace`` failure, but an injected
    exception still runs the tool's own cleanup. A killed process does not, which is the
    only way to show that write-then-move really means "an interruption leaves the previous
    bytes in place": nothing may be truncated in place, and resuming must converge on
    exactly what an uninterrupted run writes.

    The roots live under the system temp dir on purpose, not under ``tmp_path``: pytest's
    basetemp is long enough that the deepest packaged path in this tree passes Windows'
    260-character limit, and the tool then refuses with TARGET_WRITE_FAILED — a real
    behaviour of the tool, but not what this test is about.
    """
    base = Path(tempfile.gettempdir()) / ("awl-crash-%d" % os.getpid())
    if base.exists():
        shutil.rmtree(base)
    crashed_root = base / "crashed"
    clean_root = base / "clean"
    crashed_root.mkdir(parents=True)
    try:
        crashed = _run(["--apply", "--confirm", "REBUILD-MIGRATION",
                        "--target-root", str(crashed_root), "--fail-after", "40"],
                       expect=None)
        assert crashed.returncode == 9, (crashed.stdout[-400:], crashed.stderr[-400:])
        temps = sorted(p.name for p in crashed_root.rglob("*.migrating"))
        assert len(temps) <= 1, ("more than one temp means the crash was not where it is "
                                 "claimed to be: " + str(temps))
        truncated = [p.relative_to(crashed_root).as_posix()
                     for p in crashed_root.rglob("*")
                     if p.is_file() and p.suffix != ".migrating" and p.stat().st_size == 0]
        assert truncated == [], "targets were truncated in place: " + str(truncated[:5])

        resumed = _run(["--apply", "--confirm", "REBUILD-MIGRATION",
                        "--target-root", str(crashed_root)], expect=None)
        assert resumed.returncode == 0, resumed.stdout[-600:]
        assert not list(crashed_root.rglob("*.migrating")), "the resumed run left its own litter"

        clean_root.mkdir(parents=True)
        single = _run(["--apply", "--confirm", "REBUILD-MIGRATION",
                       "--target-root", str(clean_root)], expect=None)
        assert single.returncode == 0, single.stdout[-600:]

        def state(root: Path) -> dict:
            # the run manifest is excluded from the byte comparison on purpose: it records
            # its own generation time and the target root it was written for, so two
            # different roots can never agree on it. It is compared structurally below.
            return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in root.rglob("*")
                    if p.is_file() and p.suffix != ".migrating"
                    and p.relative_to(root).as_posix() != "migration/copies.json"}

        resumed_state, clean_state = state(crashed_root), state(clean_root)
        assert resumed_state == clean_state, (
            "a resumed migration did not converge on the bytes a clean run writes: "
            + str(sorted(k for k in set(resumed_state) | set(clean_state)
                         if resumed_state.get(k) != clean_state.get(k))[:10]))

        def manifest(root: Path) -> dict:
            return json.loads((root / "migration" / "copies.json").read_text(encoding="utf-8"))

        resumed_manifest, clean_manifest = manifest(crashed_root), manifest(clean_root)
        assert len(resumed_manifest["copies"]) == len(clean_manifest["copies"])
        assert (sum(entry["files"] for entry in resumed_manifest["copies"])
                == sum(entry["files"] for entry in clean_manifest["copies"]))
    finally:
        shutil.rmtree(base, ignore_errors=True)
