# SPDX-License-Identifier: MIT
"""V16: the four traceability registers must reconcile to their sources, row for row.

The fusion pack ships 56 legacy UI entries (04), 30 capability families (05), 25
explicit requirements (11) and 15 proposed endpoints (08). Before this round nothing in
the repository reconciled those tables against the code, so "PROPOSED_NOT_IMPLEMENTED"
could stay on a row that had long since been built -- or, worse, a closure document could
imply a row was done because a document said so.

What is guarded here, and deliberately **not** by reusing the builder's own resolver:

* row counts come from the source tables, read at test time -- no literal 56/30/25/15 is
  trusted that was not just counted;
* every status is inside the closed vocabulary, and the per-status histogram in
  ``api-contract-check.json`` must equal a recount of the rows;
* **no** ``IMPLEMENTED_VERIFIED`` row survives if its cited location or cited test/evidence
  key does not resolve when this test re-derives it from disk and from the live route
  tables (imported, not grepped);
* a ``EXCLUDED_BY_OWNER`` row must quote, verbatim, text that really is in its source row;
* a ``PARTIAL`` row must name what is missing;
* the 56 source rows marked ``PROPOSED_NOT_IMPLEMENTED`` may never carry an empty
  disposition;
* the builder is reproducible: running it into a scratch directory yields the same row
  counts and the same histograms as the committed registers;
* the guard actually bites -- fabricated ``file:line`` and test names fed to the builder's
  reconciler come back downgraded, so ``IMPLEMENTED_VERIFIED`` is not something an author
  can assert by writing it down.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TARGET_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = str(TARGET_ROOT / ".venv" / "Scripts" / "python.exe")
BUILDER = TARGET_ROOT / "scripts" / "build_requirement_traceability.py"
HANDOFF = TARGET_ROOT / "AI-WORK-LAB_HANDOFF_20261029"
MIGRATION = TARGET_ROOT / "migration"
EVIDENCE_DIR = TARGET_ROOT / ".project-local" / "audit" / "20261030-qoder-ed9037"

UI_SOURCE = HANDOFF / "04_原界面入口映射.csv"
FAMILY_SOURCE = HANDOFF / "05_能力族分期.csv"
REQUIREMENT_SOURCE = HANDOFF / "11_需求追溯.csv"
PROTOCOL_SOURCE = HANDOFF / "08_前后端交接约定.json"

REGISTERS = {
    "ui-entry": MIGRATION / "ui-entry-disposition.csv",
    "capability-family": MIGRATION / "capability-family-register.csv",
    "requirement": MIGRATION / "requirement-traceability.csv",
}
API_REGISTER = MIGRATION / "api-contract-check.json"

STATUSES = (
    "IMPLEMENTED_VERIFIED",
    "IMPLEMENTED_UNVERIFIED",
    "PARTIAL",
    "GAP",
    "DEFERRED_P2",
    "DEFERRED_P3",
    "EXCLUDED_BY_OWNER",
)
LOCATION_RE = re.compile(r"^(?P<path>.+):(?P<line>\d+)$")
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")


def read_source_table(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_register(path: Path) -> list[dict]:
    """Reads the register exactly the way the sibling registers are read."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def live_routes() -> dict[tuple[str, str], str]:
    for entry in (str(TARGET_ROOT), str(TARGET_ROOT / "domains" / "design")):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    from backend.v1 import V1_ROUTES
    from design_lab.http_service import ROUTES as COMPAT_ROUTES

    table = {}
    for route in V1_ROUTES:
        table[(route.method, route.pattern)] = "backend.v1.V1_ROUTES"
    for route in COMPAT_ROUTES:
        table.setdefault((route.method, route.pattern), "design_lab.http_service.ROUTES")
    return table


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("brt_v16", str(BUILDER))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_location_independently(spec: str, live: dict) -> tuple[bool, str]:
    match = re.match(r"^(%s) (/.*)$" % "|".join(METHODS), spec)
    if match:
        key = (match.group(1), match.group(2))
        if key not in live:
            return (False, "路由不在实测表中")
        return (True, "live:" + live[key])
    parsed = LOCATION_RE.match(spec)
    if not parsed:
        return (False, "位置写法不可解析")
    path = TARGET_ROOT / parsed.group("path")
    if not path.is_file():
        return (False, "文件不存在")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    number = int(parsed.group("line"))
    if number < 1 or number > len(lines) or not lines[number - 1].strip():
        return (False, "行不存在或为空")
    return (True, "file:%s:%d" % (parsed.group("path"), number))


def resolve_evidence_independently(spec: str) -> tuple[bool, str]:
    if spec == "NONE":
        return (False, "NONE")
    for part in [piece.strip() for piece in spec.split(";") if piece.strip()]:
        if part.startswith("evidence:"):
            body = part[len("evidence:"):]
            file_name, _, dotted = body.partition("#")
            path = EVIDENCE_DIR / file_name
            if not path.is_file():
                return (False, "证据文件缺失 " + file_name)
            cursor = json.loads(path.read_text(encoding="utf-8"))
            for step in [piece for piece in dotted.split(".") if piece]:
                if not isinstance(cursor, dict) or step not in cursor:
                    return (False, "键路径不存在 " + dotted)
                cursor = cursor[step]
        elif "::" in part:
            file_part, _, test_name = part.partition("::")
            path = TARGET_ROOT / file_part
            if not path.is_file():
                return (False, "测试文件缺失 " + file_part)
            if not re.search(r"^\s*def\s+%s\b" % re.escape(test_name),
                             path.read_text(encoding="utf-8", errors="replace"), re.M):
                return (False, "测试未声明 " + part)
        else:
            return (False, "证据写法不可解析 " + part)
    return (True, "resolved")


# ---------------------------------------------------------------- row counts


def test_ui_register_has_exactly_one_row_per_source_entry():
    source = read_source_table(UI_SOURCE)
    rows = read_register(REGISTERS["ui-entry"])
    assert len(source) == len(rows)
    assert len(source) > 0, "来源表读空了，计数守卫失去意义"
    # identity must be a bijection, not just the same length
    assert sorted(row["来源行标识"].split("|", 1)[1] for row in rows) == sorted(
        "%s:%s" % (row["来源仓"], row["原入口ID"]) for row in source)


def test_capability_family_register_row_count_matches_its_source():
    source = read_source_table(FAMILY_SOURCE)
    rows = read_register(REGISTERS["capability-family"])
    assert len(source) == len(rows)
    assert sorted(row["能力族ID"] for row in source) == sorted(row["能力族ID"] for row in rows)


def test_requirement_register_row_count_matches_its_source():
    source = read_source_table(REQUIREMENT_SOURCE)
    rows = read_register(REGISTERS["requirement"])
    assert len(source) == len(rows)
    assert sorted(row["需求ID"] for row in source) == sorted(row["需求ID"] for row in rows)


def test_api_register_row_count_matches_the_proposals_read_from_the_contract():
    proposals = json.loads(PROTOCOL_SOURCE.read_text(encoding="utf-8"))["api_proposals"]
    document = json.loads(API_REGISTER.read_text(encoding="utf-8"))
    assert len(proposals) == len(document["checks"])
    assert document["api_proposals_total"] == len(proposals)


# ---------------------------------------------------------------- vocabulary


def test_every_status_is_inside_the_closed_vocabulary():
    for path in list(REGISTERS.values()) + [API_REGISTER]:
        rows = (read_register(path) if path.suffix == ".csv"
                else json.loads(path.read_text(encoding="utf-8"))["checks"])
        for row in rows:
            assert row["状态"] in STATUSES, (path.name, row["来源行标识"], row["状态"])


def test_per_status_counts_sum_to_the_row_count():
    for path in list(REGISTERS.values()):
        rows = read_register(path)
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["状态"]] = counts.get(row["状态"], 0) + 1
        assert sum(counts.values()) == len(rows), path.name
    document = json.loads(API_REGISTER.read_text(encoding="utf-8"))
    recounted: dict[str, int] = {}
    for row in document["checks"]:
        recounted[row["状态"]] = recounted.get(row["状态"], 0) + 1
    assert document["status_counts"] == recounted
    assert sum(document["status_counts"].values()) == len(document["checks"])
    assert document["live_route_counts"]["v1_routes"] == 75, "实测路由数变了，登记需重跑"


# ------------------------------------------------- IMPLEMENTED_VERIFIED is real


@pytest.mark.parametrize("name", sorted(REGISTERS))
def test_no_verified_row_survives_an_unresolvable_claim(name, live_routes):
    rows = read_register(REGISTERS[name])
    offenders = []
    for row in rows:
        if row["状态"] != "IMPLEMENTED_VERIFIED":
            continue
        location_ok, location_note = resolve_location_independently(
            row["当前实现位置"], live_routes)
        evidence_ok, evidence_note = resolve_evidence_independently(row["验证证据"])
        if not (location_ok and evidence_ok):
            offenders.append((row["来源行标识"], location_note, evidence_note))
    assert not offenders, "以下行自称已核实但锚点解析失败：%s" % offenders


def test_no_api_row_claims_verified_without_a_live_route_and_a_test(live_routes):
    for row in json.loads(API_REGISTER.read_text(encoding="utf-8"))["checks"]:
        if row["状态"] != "IMPLEMENTED_VERIFIED":
            continue
        location_ok, _ = resolve_location_independently(row["当前实现位置"], live_routes)
        evidence_ok, evidence_note = resolve_evidence_independently(row["验证证据"])
        assert location_ok, row["来源行标识"]
        assert evidence_ok, (row["来源行标识"], evidence_note)
        handler_ok, _ = resolve_location_independently(row["handler位置"], live_routes)
        assert handler_ok, (row["来源行标识"], row["handler位置"])
        # the cited line must really be that handler's definition, not any non-blank line
        _file, _colon, number = row["handler位置"].rpartition(":")
        text = (TARGET_ROOT / _file).read_text(encoding="utf-8", errors="replace").splitlines()
        assert re.search(r"^\s*(def|class)\s+%s\b" % re.escape(row["handler"]),
                         text[int(number) - 1]), row["来源行标识"]


def test_verified_rows_never_cite_an_absent_location_or_no_evidence():
    for path in list(REGISTERS.values()) + [API_REGISTER]:
        rows = (read_register(path) if path.suffix == ".csv"
                else json.loads(path.read_text(encoding="utf-8"))["checks"])
        for row in rows:
            if row["状态"] == "IMPLEMENTED_VERIFIED":
                assert row["当前实现位置"] not in ("ABSENT", "", "NONE"), row["来源行标识"]
                assert row["验证证据"] != "NONE", row["来源行标识"]


# ------------------------------------------------------- exclusion and partial


def _carries_content(path: Path, line: str) -> bool:
    """Whether the cited line actually says something, rather than being a file's shell.

    ``scripts/build_migration_map.py:1`` and ``pyproject.toml:1`` are SPDX header comments;
    ``research/candidates/CANDIDATE-TAXONOMY.json:1`` is the opening brace. Every one of them
    is a non-blank line, so the resolver above accepts them -- and an anchor that points at a
    license header proves nothing about the row that cites it.
    """
    text = line.strip()
    if not text:
        return False
    if path.suffix in (".py", ".toml", ".sh", ".cfg") or path.name == ".gitignore":
        return not text.startswith("#")
    if path.suffix in (".json",):
        return text not in ("{", "}", "[", "]", "},", "],", "{}")
    if path.suffix in (".md",):
        return text.startswith("#") or len(text) > 3
    return True


def test_anchors_on_rows_that_admit_being_unverified_still_have_to_point_somewhere(live_routes):
    """PARTIAL / UNVERIFIED / DEFERRED rows cite locations and evidence too -- and until now
    no check re-read any of them, so an invented anchor could live in the register forever.

    Honest status labels are not enough: a row may correctly say ``IMPLEMENTED_UNVERIFIED`` and
    still name a file the tree does not have, or point at a license header, and the next reader
    will treat that pointer as a place to look. The strict definition-site guard stays where it
    is (it belongs to ``IMPLEMENTED_VERIFIED``); this one covers the rest of the population and
    refuses unresolvable or content-free anchors and unresolvable evidence citations.
    """
    live = live_routes
    offenders = []
    for name, path in sorted(REGISTERS.items()):
        for row in read_register(path):
            status = row["状态"]
            if status == "IMPLEMENTED_VERIFIED":
                continue
            location = row["当前实现位置"]
            if location and location not in ("ABSENT", "NONE"):
                ok, note = resolve_location_independently(location, live)
                if not ok:
                    offenders.append((name, row["来源行标识"], status, location, note))
                    continue
                if not re.match(r"^(%s) " % "|".join(METHODS), location):
                    file_part, _, number = location.rpartition(":")
                    target = TARGET_ROOT / file_part
                    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
                    if not _carries_content(target, lines[int(number) - 1]):
                        offenders.append((name, row["来源行标识"], status, location,
                                          "锚点行没有内容（许可头/括号壳）"))
            evidence = row.get("验证证据", "")
            if evidence and evidence != "NONE":
                if evidence.startswith("evidence:") or ";evidence:" in evidence:
                    offenders.append((name, row["来源行标识"], status, evidence,
                                      "未验证行的证据列引用了未运行记录本身"))
                    continue
                ok, note = resolve_evidence_independently(evidence)
                if not ok:
                    offenders.append((name, row["来源行标识"], status, evidence, note))
            for pointer in row.get("依据说明", "").split("；"):
                pointer = pointer.rstrip("）")
                if pointer.startswith("evidence:"):
                    ok, note = resolve_evidence_independently("evidence:" + pointer[len("evidence:"):])
                    if not ok:
                        offenders.append((name, row["来源行标识"], status, pointer, note))
    assert not offenders, "自称未核实的行仍然挂了无效锚点：%s" % offenders[:12]

def test_excluded_rows_quote_a_decision_that_is_actually_in_their_source_row():
    sources = {
        "ui-entry": {(row["来源仓"] + ":" + row["原入口ID"]):
                     " ".join([row["原名称"], row["拟融合位置"], row["分期"]])
                     for row in read_source_table(UI_SOURCE)},
        "requirement": {row["需求ID"]: " ".join([row["来源性质"], row["需求"], row["交付或验收"]])
                        for row in read_source_table(REQUIREMENT_SOURCE)},
    }
    found = 0
    for name, path in REGISTERS.items():
        for row in read_register(path):
            if row["状态"] != "EXCLUDED_BY_OWNER":
                continue
            found += 1
            source_text = sources.get(name, {}).get(row["来源行标识"].split("|", 1)[1], "")
            quoted = re.findall(r"「([^」]+)」", row["依据说明"])
            assert any(token in source_text for token in quoted), (
                row["来源行标识"], "声称 owner 排除，但引用的原话不在来源行里", quoted)
            assert row["当前实现位置"] == "ABSENT" or "workbench" in row["当前实现位置"]
    assert found >= 1, "没有任何 EXCLUDED_BY_OWNER 行——排除面未被本测试覆盖"


def test_partial_rows_name_what_is_missing():
    checked = 0
    for path in list(REGISTERS.values()) + [API_REGISTER]:
        rows = (read_register(path) if path.suffix == ".csv"
                else json.loads(path.read_text(encoding="utf-8"))["checks"])
        for row in rows:
            if row["状态"] == "PARTIAL":
                checked += 1
                assert "缺口：" in row["依据说明"], row["来源行标识"]
    assert checked > 0, "没有 PARTIAL 行，该守卫没有覆盖到任何东西"


def test_gap_rows_explain_themselves():
    for path in list(REGISTERS.values()) + [API_REGISTER]:
        rows = (read_register(path) if path.suffix == ".csv"
                else json.loads(path.read_text(encoding="utf-8"))["checks"])
        for row in rows:
            if row["状态"] == "GAP":
                assert len(row["依据说明"].strip()) > 20, row["来源行标识"]


# ------------------------------------------- the 56 PROPOSED_NOT_IMPLEMENTED rows


def test_no_proposed_ui_row_is_left_without_a_disposition():
    source = read_source_table(UI_SOURCE)
    proposed = [row for row in source if row["状态"] == "PROPOSED_NOT_IMPLEMENTED"]
    assert len(proposed) == len(source), "来源表状态口径已变，本测试需重读"
    rows = {row["来源行标识"].split("|", 1)[1]: row
            for row in read_register(REGISTERS["ui-entry"])}
    for entry in proposed:
        key = entry["来源仓"] + ":" + entry["原入口ID"]
        row = rows[key]
        for column in ("当前实现位置", "验证证据", "状态", "依据说明"):
            assert row[column].strip(), (key, column)
        assert row["状态"] in STATUSES, key
        assert row["来源表状态"] == "PROPOSED_NOT_IMPLEMENTED", key
        # a disposition that says "still proposed" in different words is not a
        # disposition: it must commit to one of the seven outcomes
        assert row["状态"] != "PROPOSED_NOT_IMPLEMENTED"


# ------------------------------------------------------------ reproducibility


def test_builder_is_reproducible_into_a_scratch_directory(tmp_path):
    completed = subprocess.run(
        [VENV_PYTHON, "-B", "-X", "utf8", str(BUILDER), "--out-dir", str(tmp_path)],
        cwd=str(TARGET_ROOT), capture_output=True, text=True, timeout=1200,
        encoding="utf-8", errors="replace")
    assert completed.returncode == 0, completed.stderr[-2000:]
    # the console must stay cp936-safe: machine-readable summary, ASCII-escaped
    assert "\\u" in completed.stdout, "摘要未按 ensure_ascii=True 输出"
    json.loads(completed.stdout)
    for name, path in REGISTERS.items():
        fresh = read_register(tmp_path / path.name)
        assert len(fresh) == len(read_register(path)), name
        recount = {}
        for row in read_register(tmp_path / path.name):
            recount[row["状态"]] = recount.get(row["状态"], 0) + 1
        committed = {}
        for row in read_register(path):
            committed[row["状态"]] = committed.get(row["状态"], 0) + 1
        assert recount == committed, name
    fresh_api = json.loads((tmp_path / API_REGISTER.name).read_text(encoding="utf-8"))
    committed_api = json.loads(API_REGISTER.read_text(encoding="utf-8"))
    assert [row["状态"] for row in fresh_api["checks"]] == [
        row["状态"] for row in committed_api["checks"]]


# --------------------------------------------------------- the guard must bite


def test_fabricated_anchors_are_downgraded_by_the_builder(builder, tmp_path):
    """A claim an author invented must not survive as IMPLEMENTED_VERIFIED.

    Fed through the builder's own reconciler with a scratch copy of the judgement -- the
    committed registers are never touched here.
    """
    fake_location = {
        "location": "backend/v1.py:999999",
        "evidence": "tests/unified/test_v02_surface.py::test_health_is_real_service_metadata",
        "status": "IMPLEMENTED_VERIFIED", "basis": "伪造行号",
    }
    downgraded = builder.reconcile("scratch", "T#L1|x", "要求", "", fake_location)
    assert downgraded["状态"] == "GAP", downgraded["依据说明"][-160:]

    fake_blank_line = {"location": "backend/v1.py:130", "evidence": "NONE",
                       "status": "PARTIAL", "basis": "该行是空行，不能当位置"}
    blank = builder.reconcile("scratch", "T#L1|y", "要求", "", fake_blank_line)
    assert blank["状态"] in ("GAP",), blank["依据说明"][-160:]

    fake_test = {"location": "backend/v1.py:146",
                 "evidence": "tests/unified/test_v02_surface.py::test_no_such_test_anywhere",
                 "status": "IMPLEMENTED_VERIFIED", "basis": "伪造测试名"}
    unver = builder.reconcile("scratch", "T#L1|z", "要求", "", fake_test)
    assert unver["状态"] == "IMPLEMENTED_UNVERIFIED", unver["依据说明"][-160:]

    fake_route = {"location": "GET /api/v1/does-not-exist",
                  "evidence": "tests/unified/test_v02_surface.py::test_health_is_real_service_metadata",
                  "status": "IMPLEMENTED_VERIFIED", "basis": "伪造路由"}
    gone = builder.reconcile("scratch", "T#L1|w", "要求", "", fake_route)
    assert gone["状态"] == "GAP", gone["依据说明"][-160:]

    fake_evidence_file = {"location": "backend/v1.py:146",
                          "evidence": "evidence:a01-a10-results.json#results.NO_SUCH_KEY",
                          "status": "IMPLEMENTED_VERIFIED", "basis": "伪造证据键"}
    ev_gone = builder.reconcile("scratch", "T#L1|v", "要求", "", fake_evidence_file)
    assert ev_gone["状态"] == "IMPLEMENTED_UNVERIFIED", ev_gone["依据说明"][-160:]

    invented_exclusion = {"location": "ABSENT", "evidence": "NONE",
                          "status": "EXCLUDED_BY_OWNER", "decision_quotes": ["owner 从未说过的话"],
                          "basis": "「owner 从未说过的话」"}
    excluded = builder.reconcile("scratch", "T#L1|u", "真实来源文字", "", invented_exclusion)
    assert excluded["状态"] == "GAP", excluded["依据说明"][-160:]

    unbacked_deferral = {"location": "ABSENT", "evidence": "NONE",
                         "status": "DEFERRED_P3", "basis": "没有分期依据"}
    deferred = builder.reconcile("scratch", "T#L1|t", "P1保留合并与修复", "", unbacked_deferral)
    assert deferred["状态"] == "GAP", deferred["依据说明"][-160:]

    assert not (tmp_path / "unused").exists()


def test_every_register_row_carries_the_six_required_columns():
    required = ["来源行标识", "要求原文", "当前实现位置", "验证证据", "状态", "依据说明"]
    for path in list(REGISTERS.values()):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle))
        for column in required:
            assert column in header, (path.name, column)
    for row in json.loads(API_REGISTER.read_text(encoding="utf-8"))["checks"]:
        for column in required:
            assert column in row, (row["来源行标识"], column)


def test_the_four_registers_are_the_only_migration_artefacts_this_builder_writes():
    """The declared outputs exist, and nothing was left half-written.

    Scope discipline is asserted on the builder rather than on ``git status``: other
    agents are editing this tree concurrently, so a working-tree check would fail for
    reasons unrelated to this register. What is owned here is that every write target of
    this builder is one of the four declared registers, and that no existing migration
    artefact appears as a write target anywhere in its source.
    """
    expected = {"ui-entry-disposition.csv", "capability-family-register.csv",
                "requirement-traceability.csv", "api-contract-check.json"}
    for name in expected:
        assert (MIGRATION / name).is_file(), name
    assert not list(MIGRATION.glob("*.tmp")), "登记写出留下临时文件"
    builder_source = BUILDER.read_text(encoding="utf-8")
    write_targets = re.findall(r'args\.out_dir / "([^"]+)"', builder_source)
    assert set(write_targets) == expected, write_targets
    #: the four handoff tables are read-only inputs -- no line that touches one of them
    #: may also be a write
    for token in ("UI_TABLE", "FAMILY_TABLE", "REQUIREMENT_TABLE", "PROTOCOL_TABLE",
                  "PHASING_TABLE", "EVIDENCE_DIR"):
        for line in builder_source.splitlines():
            if token in line:
                assert "write_text" not in line and 'open("w"' not in line, (token, line)


#: source paths may contain Chinese directory names, so the class allows them; the
#: extension alternation is longest-first or ".tsx" parses as ".ts" plus a stray letter
_CITATION_RE = re.compile(r"([A-Za-z0-9_./一-鿿-]+\.(?:tsx|jsx|py|json|md|ts))"
                         r"(?::(\d+))?")
_SEAM_ID_RE = re.compile(r"(?<![A-Za-z0-9_])[a-z][a-z0-9]*\.[a-z][a-z0-9_]*(?![A-Za-z0-9_])")


def test_absent_rows_cite_evidence_for_saying_the_surface_never_existed():
    """A GAP row with no implementation location must name the concrete evidence behind that.

    "本仓没有这个端点" is checkable, but the sentence explaining *why* the entry is missing --
    "来源侧也从来没有后端面，不是融合时丢的", or "保留的是接缝" -- needs a pointer somebody can
    go read. Until now several of these rows asserted that with no citation at all, so a
    reviewer could not tell "verified absent" from "guessed absent".
    """
    deferral_ids = {entry["id"] for entry in
                    json.loads((TARGET_ROOT / "migration/deferral-register.json")
                               .read_text(encoding="utf-8-sig"))["entries"]}
    work_source = TARGET_ROOT.parent / "WORK-LAB"
    rows = read_register(REGISTERS["ui-entry"])
    resolved = 0
    for row in rows:
        if row["状态"] != "GAP" or row["当前实现位置"] != "ABSENT":
            continue
        basis = row["依据说明"]
        citations = _CITATION_RE.findall(basis)
        assert citations, (row["来源行标识"], "没有可去读的出处，无法区分「已核实为不存在」与「猜的不存在」")
        for path_text, number in citations:
            target = TARGET_ROOT / path_text
            if not target.is_file() and work_source.is_dir():
                target = work_source / path_text
            assert target.is_file(), (row["来源行标识"], path_text)
            if number:
                lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
                assert 0 < int(number) <= len(lines), (row["来源行标识"], path_text, number)
            if path_text.endswith("deferral-register.json"):
                named = [token for token in _SEAM_ID_RE.findall(basis) if token in deferral_ids]
                assert named, (row["来源行标识"], "点了登记文件却没有真实的条目 id：%s" % sorted(deferral_ids))
            resolved += 1
    assert resolved >= 7, (
        "只有 %d 条出处被复核——7 行 GAP 各自都该点名来源侧的端点清单、前端路由或接缝条目，"
        "少于此说明出处又退回了无指向的叙述" % resolved)
