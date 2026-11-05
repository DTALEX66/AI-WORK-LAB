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

import ast as _ast
import csv
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

TARGET_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TARGET_ROOT / "scripts"))
import source_roots  # noqa: E402  the one place roots outside this checkout are resolved
#: venv 解释器的布局是平台的，不是机器的：Windows 是 Scripts/python.exe，POSIX 是 bin/python（审计 N05）。
VENV_PYTHON = str(TARGET_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
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
    repo_state = re.match(r"^repo:(?P<what>[\w-]+)$", spec)
    if repo_state:
        # a repository-state claim is answered by git, independently of the generator's own helper:
        # only `repo:branch` exists, and it is true exactly where a branch is checked out
        if repo_state.group("what") != "branch":
            return (False, "未知的 repo: 形态 repo:%s" % repo_state.group("what"))
        out = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=str(TARGET_ROOT),
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        name = (out.stdout or "").strip()
        if out.returncode != 0 or not name:
            return (False, "HEAD 是分离的，没有检出的分支")
        return (True, "branch:" + name)
    symbol = re.match(r"^(?P<path>[^:]+)::(?P<name>[A-Za-z_]\w*)$", spec)
    if symbol:
        # a name anchor resolves against the file, not against an offset: it is there exactly once,
        # as a def/class header or a module-level binding, and that is the whole claim
        path = TARGET_ROOT / symbol.group("path")
        if not path.is_file():
            return (False, "文件不存在")
        name = symbol.group("name")
        header = re.compile(r"^(?:\s*(?:def|class)\s+%s\b|%s\s*[:=])"
                            % (re.escape(name), re.escape(name)))
        hits = [text for text in path.read_text(encoding="utf-8", errors="replace").splitlines()
                if header.match(text)]
        if not hits:
            return (False, "文件里没有名为 %s 的定义或模块级绑定" % name)
        if len(hits) > 1:
            return (False, "%s 在该文件出现 %d 次，锚点说不出是哪一个" % (name, len(hits)))
        return (True, "symbol:%s::%s" % (symbol.group("path"), name))
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
            file_part, _, remainder = part.partition("::")
            path = TARGET_ROOT / file_part
            if not path.is_file():
                return (False, "测试文件缺失 " + file_part)
            # re-derived here rather than borrowed from the builder: a citation is only evidence if
            # pytest could collect it, and pytest spells a TestCase method as ``Class::method``.
            # Grepping for a ``def`` line anywhere accepted ``file.py::test_method`` for the four
            # legacy design files, where that id answers "no tests ran".
            tree = _ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            collectible = {node.name for node in tree.body
                           if isinstance(node, _ast.FunctionDef)
                           and node.name.startswith("test_")}
            for node in tree.body:
                if isinstance(node, _ast.ClassDef):
                    collectible.update("%s::%s" % (node.name, item.name) for item in node.body
                                       if isinstance(item, _ast.FunctionDef)
                                       and item.name.startswith("test_"))
            if remainder not in collectible:
                return (False, "pytest 收不到 " + part)
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
        # the cited construct must really be that handler's definition, not any non-blank line
        named, why = cite_names_the_handler(row["handler位置"], row["handler"])
        assert named, (row["来源行标识"], row["handler位置"], why)


def cite_names_the_handler(spec: str, handler: str) -> tuple[bool, str]:
    """The cite must point at *this* route's handler definition, in whichever anchor form it uses.

    ``file::name`` says it by name, so the check is that the name is the handler's; ``file:line`` says
    it by offset, so the check is that the line really is a ``def``/``class`` header for the handler.
    Both branches are asserted because the register can emit either -- the number is what is left when
    a name occurs twice in the file, and that fallback has to stay honest too.
    """
    if "::" in spec:
        anchor = spec.split("::", 1)[1]
        return (anchor == handler, "符号锚叫的是 %s，不是这一行的 handler %s" % (anchor, handler))
    path, _colon, number = spec.rpartition(":")
    text = (TARGET_ROOT / path).read_text(encoding="utf-8", errors="replace").splitlines()
    hit = re.search(r"^\s*(def|class)\s+%s\b" % re.escape(handler), text[int(number) - 1])
    return (bool(hit), "行号锚没有落在 %s 的 def/class 上" % handler)


def test_a_repository_state_claim_is_answered_by_git_and_no_location_lives_inside_git(builder,
                                                                                     tmp_path):
    """U11 used to cite ``.git/HEAD:1`` as its implementation location; that address is not auditable.

    Bytes under ``.git/`` are outside ``git ls-files``, cannot be diffed between clones, and change
    meaning with the checkout: this project's clone-repro harness checks commits out *detached*, and a
    detached ``.git/HEAD`` holds a bare SHA where a branch ref used to be -- the line was still there
    and still non-empty, so a guard that only asks "does this line exist" stayed green at exactly the
    moment the claim ("this work happens on a checked-out local branch") stopped being true. Two rules
    close it, and both are planted here: ``.git/`` paths are refused as locations, and ``repo:branch``
    is answered by git, refusing when the checkout is detached. The duplicate module-level binding that
    forced U10 back to a line number is pinned in the same pass, because that is how #32 was found.
    """
    refused = builder.check_location(".git/HEAD:1")
    assert refused[0] is False and ".git/" in refused[1], refused

    on_branch = builder.check_location("repo:branch")
    assert on_branch[0] is True and "symbolic-ref" in on_branch[1], on_branch
    assert builder.check_location("repo:whatever")[0] is False, "未知 repo: 形态被当成可解析"

    # the detached case, built rather than described: a throwaway repo whose HEAD is a bare SHA
    sandbox = tmp_path / "detached"
    sandbox.mkdir()
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@invalid")
    for args in (["init", "-q", "--initial-branch=main"], ["commit", "-q", "--allow-empty",
                                                           "-m", "one"]):
        assert subprocess.run(["git", *args], cwd=str(sandbox), env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace").returncode == 0, args
    assert subprocess.run(["git", "checkout", "-q", "--detach"], cwd=str(sandbox), env=env,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace").returncode == 0
    head_bytes = (sandbox / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    assert not head_bytes.startswith("ref:"), head_bytes
    original = builder.REPO_ROOT
    builder.REPO_ROOT = sandbox
    try:
        detached = builder.check_location("repo:branch")
        assert detached[0] is False and "分离" in detached[1], detached
        # and this is where the old shape lied: the line exists and is non-empty inside .git/,
        # so a content-blind guard would still have called U11 verified -- now it is refused by rule
        assert (sandbox / ".git" / "HEAD").is_file()
        assert builder.check_location(".git/HEAD:1")[0] is False
    finally:
        builder.REPO_ROOT = original

    # no published register may carry a .git/ path *as a location* -- the 依据说明 column is allowed to
    # name the old shape, because that is how the追正 says what was replaced
    offenders = []
    for name, path in sorted(list(REGISTERS.items()) + [("api-contract", API_REGISTER)]):
        rows = (read_register(path) if path.suffix == ".csv" else
                json.loads(path.read_text(encoding="utf-8-sig")).get("checks", []))
        for row in rows:
            for column, value in row.items():
                if not isinstance(value, str) or "说明" in column or "原因" in column:
                    continue
                if value.replace("\\", "/").lstrip("\"").startswith(".git/") or "/.git/" in value:
                    offenders.append((name, column, value[:40]))
    assert offenders == [], "登记里又出现了 .git/ 内部路径作为位置：%s" % offenders[:4]

    # the root cause of the U10 fallback: one module-level binding, not two
    tree = _ast.parse((TARGET_ROOT / "backend" / "v1.py").read_text(encoding="utf-8-sig"))
    bindings = [node.lineno for node in tree.body if isinstance(node, _ast.Assign)
                and any(isinstance(t, _ast.Name) and t.id == "V1_ROUTES" for t in node.targets)]
    assert len(bindings) == 1, ("V1_ROUTES 又被绑了多次，登记只能退回行号：%s" % bindings)
    assert builder.find_binding("V1_ROUTES", "backend/v1.py") == "backend/v1.py::V1_ROUTES"
    assert builder.check_location("backend/v1.py::V1_ROUTES")[0] is True


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
            location = row["当前实现位置"]
            if location and location not in ("ABSENT", "NONE"):
                ok, note = resolve_location_independently(location, live)
                if not ok:
                    offenders.append((name, row["来源行标识"], status, location, note))
                    continue
                if not re.match(r"^(%s) " % "|".join(METHODS), location):
                    if location.startswith("repo:"):
                        # a repository-state claim was answered by git above; there is no line to read
                        continue
                    if "::" in location:
                        # a name anchor is checked against the line it names: the resolver proved the
                        # name exists once, this proves the thing it names has content -- a licence
                        # header or a brace shell cannot be a def header or a module binding
                        rel, anchor = location.split("::", 1)
                        target = TARGET_ROOT / rel
                        header = re.compile(r"^(?:\s*(?:def|class)\s+%s\b|%s\s*[:=])"
                                            % (re.escape(anchor), re.escape(anchor)))
                        hit = [text for text in target.read_text(encoding="utf-8", errors="replace")
                               .splitlines() if header.match(text)]
                        if not hit or not _carries_content(target, hit[0]):
                            offenders.append((name, row["来源行标识"], status, location,
                                              "符号锚解析不出有内容的定义行"))
                        continue
                    file_part, _, number = location.rpartition(":")
                    target = TARGET_ROOT / file_part
                    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
                    if not _carries_content(target, lines[int(number) - 1]):
                        offenders.append((name, row["来源行标识"], status, location,
                                          "锚点行没有内容（许可头/括号壳）"))
            evidence = row.get("验证证据", "")
            if status == "IMPLEMENTED_VERIFIED":
                # the strict guard above already resolves a VERIFIED row's evidence; the
                # content-of-the-anchor rule is shared, because that is what let a `{` line
                # pass as the location of a row claiming verification
                continue
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

def _declared_test_names(text: str) -> list[str]:
    """Collectible node names an author wrote down, spelled the way pytest spells them.

    Module-level functions are bare names; a ``TestCase`` method collects as ``Class::method``,
    which is the only citation form that resolves for the four legacy design files.
    """
    tree = _ast.parse(text)
    names = [n.name for n in tree.body if isinstance(n, _ast.FunctionDef)
             and n.name.startswith("test_")]
    for node in tree.body:
        if isinstance(node, _ast.ClassDef):
            names.extend("%s::%s" % (node.name, item.name) for item in node.body
                         if isinstance(item, _ast.FunctionDef) and item.name.startswith("test_"))
    return names


def _def_line_count(text: str) -> int:
    """How many lines *look* like a test definition, whether or not they define anything."""
    return len([line for line in text.splitlines() if line.strip().startswith("def test_")])


def test_every_cited_test_node_is_collected_by_pytest_and_every_file_collects_what_it_declares():
    """The registers cite nodes; this checks pytest can actually see them.

    Resolving a citation by grepping ``def <name>`` proves the words are in the file, not that a
    test exists there. When an anchored insert ate one ``def`` line, the orphaned body silently
    joined the preceding test: the file still imported, the suite still passed, and only the
    register build noticed the missing name. So the population here is enumerated from pytest's
    own collection report over the cited files, and two things must hold -- every cited node id is
    collected, and each cited file collects exactly as many items as it declares functions.
    """
    cited: dict[str, set[str]] = {}
    for path in sorted(REGISTERS.values()) + [API_REGISTER]:
        rows = (read_register(path) if path.suffix == ".csv"
                else json.loads(path.read_text(encoding="utf-8"))["checks"])
        for row in rows:
            for part in [piece.strip() for piece in row.get("验证证据", "").split(";") if piece.strip()]:
                if "::" in part and part.startswith("tests/"):
                    file_part, _, name = part.partition("::")
                    cited.setdefault(file_part, set()).add(name)
    assert cited, "no register cites a test node at all, so this guard would be vacuous"

    files = sorted(cited)
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *files],
        cwd=str(TARGET_ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=900)
    assert collected.returncode == 0, collected.stdout[-3000:] + collected.stderr[-3000:]
    seen: dict[str, set[str]] = {}
    for line in collected.stdout.splitlines():
        marker = "::"
        if marker in line and line.startswith("tests/"):
            file_part, _, name = line.partition("::")
            seen.setdefault(file_part.strip(), set()).add(name.strip())

    missing = [(file_part, name) for file_part, names in sorted(cited.items())
               for name in sorted(names) if name not in seen.get(file_part, set())]
    assert missing == [], "登记表引用的节点 pytest 收不到：%s" % missing[:10]

    drift = []
    for file_part in files:
        text = (TARGET_ROOT / file_part).read_text(encoding="utf-8", errors="replace")
        declared, collected_names = _declared_test_names(text), seen.get(file_part, set())
        # A parametrised node collects as test_x[case]; the register cites the bare name, and a
        # file may declare one function that pytest hands back as several ids.
        if len(declared) != len(set(declared)):
            drift.append((file_part, "duplicate declarations",
                          sorted([n for n in declared if declared.count(n) > 1])))
        if not set(declared) <= collected_names:
            drift.append((file_part, "declared but not collected",
                          sorted(set(declared) - collected_names)[:5]))
        if {name.split("[")[0] for name in collected_names} != set(declared):
            drift.append((file_part, "collected but not declared",
                          sorted({name.split("[")[0] for name in collected_names}
                                 - set(declared))[:5]))
        if _def_line_count(text) != len(declared):
            drift.append((file_part, "def-lines", _def_line_count(text),
                          "declared", len(declared)))
    assert drift == [], "某个被引用的测试文件收进来的与声明的对不上（吞掉的 def 行就在这一列露出来）：%s" % drift


def test_the_collect_predicate_names_an_absorbed_def_line(tmp_path):
    """The guard above can see the fault it exists for: a planted file whose body has no ``def``.

    Without this, ``_declared_test_names`` would be trusted because it agrees with pytest on the
    healthy tree -- which is also what it does on a broken one. Here the second test's ``def`` line
    is deleted, leaving an indented body that attaches to the first test: the module still imports,
    so the syntax-tree count drops to one while the ``def test_`` line count drops with it. The
    pair the real guard compares is the collected set against the declared names, and the
    collected-vs-def-line mismatch is what a reviewer needs to see.
    """
    healthy = ("def test_one():\n    assert 1 == 1\n\n"
               "def test_two():\n    assert 2 == 2\n")
    assert _declared_test_names(healthy) == ["test_one", "test_two"]
    assert _def_line_count(healthy) == 2

    absorbed = "def test_one():\n    assert 1 == 1\n\n    assert 2 == 2\n"
    tree_names = _declared_test_names(absorbed)
    assert tree_names == ["test_one"], tree_names
    assert _def_line_count(absorbed) == 1

    written = tmp_path / "test_planted_absorption.py"
    written.write_text(absorbed, encoding="utf-8")
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", str(written)],
        cwd=str(tmp_path.parent), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300)
    assert "test_one" in collected.stdout and "test_two" not in collected.stdout, collected.stdout


def _run_builder(out_dir) -> int:
    """Build the four registers into ``out_dir`` the way the tracked copies were built."""
    completed = subprocess.run(
        [sys.executable, str(BUILDER), "--out-dir", str(out_dir)],
        cwd=str(TARGET_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=900)
    assert completed.returncode == 0, completed.stdout[-2000:] + completed.stderr[-2000:]
    return completed.returncode


def test_rebuilding_over_the_published_registers_does_not_relamp_them(tmp_path):
    """A no-content rebuild must leave the tracked bytes alone, including the recorded moment.

    ``migration/api-contract-check.json`` carries a ``generated_at`` and is tracked, while the
    audited candidate digest is a hash over tracked bytes: a builder that rewrites the stamp on an
    unchanged payload moves the digest of a candidate that did not move. So the register is rebuilt
    here over a copy of the published files and must come back byte-identical -- and the claim is
    then falsified by rebuilding into an empty directory, where the only permitted difference is
    exactly that stamp field. A build that always restamps fails the first half; a comparison that
    ignored the stamp would pass both halves and guard nothing.
    """
    registers = ["ui-entry-disposition.csv", "capability-family-register.csv",
                 "requirement-traceability.csv", "api-contract-check.json"]
    published = {}
    for name in registers:
        raw = (MIGRATION / name).read_bytes()
        (tmp_path / name).write_bytes(raw)
        published[name] = raw

    _run_builder(tmp_path)
    relamped = [name for name in registers if (tmp_path / name).read_bytes() != published[name]]
    assert relamped == [], "内容未变的登记表被改写：%s" % relamped

    fresh = tmp_path / "fresh"
    fresh.mkdir()
    _run_builder(fresh)
    fresh_document = json.loads((fresh / "api-contract-check.json").read_text(encoding="utf-8"))
    published_document = json.loads((MIGRATION / "api-contract-check.json")
                                    .read_text(encoding="utf-8"))
    assert fresh_document["generated_at"] != published_document["generated_at"], (
        "两份不同检出写下同一个时刻，本节的第一条断言就没有可比的东西")
    fresh_document.pop("generated_at")
    published_document.pop("generated_at")
    assert json.dumps(fresh_document, sort_keys=True) == json.dumps(published_document,
                                                                    sort_keys=True), (
        "跟踪的登记表与现算结果在内容上就不一致了，本节第一条的字节相等只是因为两边一起过时")


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

    # the three planted locations are positions in a file this test does not own, so they are derived
    # from the current tree rather than hard-coded: a literal `backend/v1.py:195` broke the day a line
    # was deleted 46 lines above it, and a guard that only fires on an accident is not a guard
    v1_lines = (TARGET_ROOT / "backend" / "v1.py").read_text(encoding="utf-8-sig").splitlines()
    v1_tree = _ast.parse("\n".join(v1_lines))
    blank_at = next(number for number, text in enumerate(v1_lines, 1) if not text.strip())
    inside_at = next(number for node in _ast.walk(v1_tree) if isinstance(node, _ast.FunctionDef)
                     for number in range(node.lineno + 1, node.end_lineno or node.lineno + 1)
                     if v1_lines[number - 1].strip()
                     and not builder.ANCHOR_FORM_RE.match(v1_lines[number - 1]))
    definition_at = next(node.lineno for node in _ast.walk(v1_tree)
                         if isinstance(node, _ast.FunctionDef))

    fake_blank_line = {"location": "backend/v1.py:%d" % blank_at, "evidence": "NONE",
                       "status": "PARTIAL", "basis": "该行是空行，不能当位置"}
    blank = builder.reconcile("scratch", "T#L1|y", "要求", "", fake_blank_line)
    assert blank["状态"] in ("GAP",), blank["依据说明"][-160:]

    # a line inside a function body is not "the implementation": the row reads as resolved
    # while pointing at a statement that names nothing. This is how an anchor drifts once
    # anything above it grows, so the builder refuses it even though the line exists.
    drifted_anchor = {"location": "backend/v1.py:%d" % inside_at,
                      "evidence": "tests/unified/test_v02_surface.py::test_health_is_real_service_metadata",
                      "status": "IMPLEMENTED_VERIFIED", "basis": "锚点落在函数体的一行"}
    slid = builder.reconcile("scratch", "T#L1|s", "要求", "", drifted_anchor)
    assert slid["状态"] == "GAP", slid["依据说明"][-200:]
    assert "不是定义行" in slid["依据说明"], slid["依据说明"][-200:]

    fake_test = {"location": "backend/v1.py:%d" % definition_at,
                 "evidence": "tests/unified/test_v02_surface.py::test_no_such_test_anywhere",
                 "status": "IMPLEMENTED_VERIFIED", "basis": "伪造测试名"}
    unver = builder.reconcile("scratch", "T#L1|z", "要求", "", fake_test)
    assert unver["状态"] == "IMPLEMENTED_UNVERIFIED", unver["依据说明"][-160:]

    fake_route = {"location": "GET /api/v1/does-not-exist",
                  "evidence": "tests/unified/test_v02_surface.py::test_health_is_real_service_metadata",
                  "status": "IMPLEMENTED_VERIFIED", "basis": "伪造路由"}
    gone = builder.reconcile("scratch", "T#L1|w", "要求", "", fake_route)
    assert gone["状态"] == "GAP", gone["依据说明"][-160:]

    fake_evidence_file = {"location": "backend/v1.py:%d" % definition_at,
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


def test_authored_python_locations_name_a_symbol_not_a_typed_line_number(builder, tmp_path):
    """A typed `file:line` rots the moment anything above it is edited; a symbol reference cannot.

    This round proved the point twice over: adding lines to `model_catalog.py` slid the radar
    anchor onto a dict member, and adding one declaration to `migrate_sources.py` slid the cleanup
    anchor off `def prune_report` -- both after the anchors had been re-pinned by hand. Deriving the
    number at build time stopped the *lies*; it did not stop the churn, and a later round of this
    batch measured it (152 of 294 line cites in the coverage register no longer sat in the construct
    that produced them, every one still resolving). So `find_definition` / `find_binding` now name the
    construct -- `file::name` -- and the number is only what is left when a name occurs twice. The
    shape assertions below are what stops a future edit from quietly going back to a literal, and the
    two lookups show what happens when the named thing is gone: the anchor resolves to nothing, the
    row downgrades, and no register line claims a location it cannot find.
    """
    source = BUILDER.read_text(encoding="utf-8")
    typed = re.findall(r'"location": "([\w./-]+\.py):(\d+)"', source)
    assert typed == [], "登记生成器里又出现了手抄的 python 行号锚点：%s" % typed

    import ast as _astmod
    for name, relative in (("prune_report", "scripts/migrate_sources.py"),
                           ("catalog", "domains/design/design_lab/model_catalog.py")):
        tree = _astmod.parse((TARGET_ROOT / relative).read_text(encoding="utf-8"))
        headers = [node.lineno for node in _astmod.walk(tree)
                   if isinstance(node, _astmod.FunctionDef) and node.name == name]
        # uniqueness is the anchor's whole promise: with two definitions of that name the register
        # would be citing a word, not a place, so the emitter must fall back to the number instead
        assert len(headers) == 1, (name, sorted(headers))
        assert builder.find_definition(name, relative) == "%s::%s" % (relative, name), name
    # `V1_ROUTES` used to be bound twice at module level (a `()` declaration and the assembled table),
    # which forced this cite back to the number form and pointed it at the dead first binding. That
    # declaration was removed in this round, so the name is unique and the cite is a symbol again; the
    # duplicate case is still proven, just on a sandbox file whose name really is defined twice.
    assert builder.find_binding("V1_ROUTES", "backend/v1.py") == "backend/v1.py::V1_ROUTES"
    # the fallback path is part of the contract, not a hypothetical: a name the file spells twice has
    # to come back as a number, and the number it returns has to be a real definition line. The twin
    # is written into the test's own sandbox and the builder's root is moved there, so nothing lands
    # in the repository for another guard to trip over.
    twin = tmp_path / "anchor-twin.py"
    twin.write_text("def dup():\n    return 1\n\n\ndef dup():\n    return 2\n", encoding="utf-8")
    original_root = builder.REPO_ROOT
    builder.REPO_ROOT = tmp_path
    try:
        spec = builder.find_definition("dup", "anchor-twin.py")
        assert spec == "anchor-twin.py:1", (
            "一个在文件里出现两次的名字被当成锚点写进了登记：%s" % spec)
        ok, note = builder.check_location(spec)
        assert ok is True, note
    finally:
        builder.REPO_ROOT = original_root
    assert builder.find_definition("no_such_symbol_in_this_repo", "scripts/migrate_sources.py") is None
    assert builder.find_binding("NO_SUCH_BINDING", "backend/v1.py") is None
    # and the resolver refuses an anchor whose name has been renamed away, or written badly -- a row
    # cannot keep claiming a place that no longer exists
    assert builder.check_location("scripts/migrate_sources.py::prune_report renamed")[0] is False
    missing = builder.check_location("scripts/migrate_sources.py::prune_reportX")
    assert missing[0] is False and "没有名为" in missing[1], missing


#: `file.py#symbol`. A realm-prefixed key (`design:src/...py#L144`) is left out by the optional
#: group below: those are source-repository identity keys quoted in the migration map, not
#: citations of this checkout's code, and this node cannot resolve a file it does not carry.
PROSE_SYMBOL_CITE = re.compile(r"(?:(?P<realm>[a-z_]+):)?([A-Za-z0-9_./-]+\.py)#"
                               r"([A-Za-z_][A-Za-z0-9_]*)")
PROSE_SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv"}
#: A `#L144` fragment is a GitHub line permalink, not a symbol reference -- a different convention,
#: used by `scripts/build_migration_map.py` for links into the source repos. It rots the same way a
#: typed number does, and it is out of this node's scope; naming it here keeps the exclusion honest
#: instead of silently shrinking the population.
LINE_PERMALINK = re.compile(r"^L\d+$")
#: The citation grammar is necessarily written out in this file, so its own examples would be
#: judged by the rule they define (same reason the clone instrument excludes `test_v23`).
SELF_FILE = "tests/unified/test_v16_traceability.py"


def prose_symbol_citations(root: Path) -> list:
    """Every `file.py#symbol` citation written in this checkout's own Python prose.

    ``root`` is a parameter so a counter-example can point the scan at a planted tree; the same
    reason ``_active_python_files`` takes one in the clone instrument.
    """
    found = []
    for path in sorted(list(root.glob("scripts/*.py")) + list(root.glob("tests/**/*.py"))):
        if PROSE_SKIP_PARTS & set(path.parts):
            continue
        if path.relative_to(root).as_posix() == SELF_FILE:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in PROSE_SYMBOL_CITE.finditer(line):
                if match.group("realm") or LINE_PERMALINK.match(match.group(3)):
                    continue
                found.append({"from": "%s:%d" % (path.relative_to(root).as_posix(), line_number),
                              "file": match.group(2), "symbol": match.group(3)})
    return found


def unresolved_prose_symbol_citations(root: Path) -> list:
    """Citations whose named object is not a def/class/assignment in the file they point at."""
    definition = re.compile(r"(?:^|\s)(?:def|class)\s+%s\b|%s\s*=" %
                            ((re.escape(c["symbol"]),) * 2) if False else r"(?:def|class)\s+")
    offenders = []
    cache = {}
    for cite in prose_symbol_citations(root):
        target = root / cite["file"]
        if not target.is_file():
            offenders.append(dict(cite, why="FILE_ABSENT"))
            continue
        if target not in cache:
            cache[target] = target.read_text(encoding="utf-8", errors="replace")
        body = cache[target]
        pattern = re.compile(r"(?:def|class)\s+%s\s*[(:]|%s\s*=" %
                             (re.escape(cite["symbol"]), re.escape(cite["symbol"])))
        if not pattern.search(body):
            offenders.append(dict(cite, why="SYMBOL_NOT_IN_TARGET"))
    return offenders


def test_prose_symbol_citations_in_this_checkout_all_resolve():
    """#14's durable half: a citation by name is only better than a number if it still resolves.

    The register columns already refuse typed line numbers (see
    ``test_authored_python_locations_name_a_symbol_not_a_typed_line_number``); the same failure mode
    lives in comments -- nine `backend/v1.py:NNN` cites in test prose, of which seven had drifted
    (six of them before this batch even started, which is what makes the format the defect rather
    than any one edit). They now read `backend/v1.py#_v1_import_result` and this node is what stops
    a future `#_renamed_thing` from sitting there unclaimed.
    """
    cites = prose_symbol_citations(TARGET_ROOT)
    assert cites, "没有任何 `file.py#symbol` 引用被扫到：这条判据可能只是在检查空集合"
    offenders = unresolved_prose_symbol_citations(TARGET_ROOT)
    assert offenders == [], "注释里的符号引用指不到真东西：%s" % offenders


def test_falsification_a_planted_symbol_citation_is_named(tmp_path):
    """The resolver has to be able to go red: plant one good cite and two broken ones."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "scripts" / "real_helper.py").write_text(
        "def keep_me():\n    return 1\n", encoding="utf-8")
    (tmp_path / "tests" / "t_prose.py").write_text(
        '"""doc: scripts/real_helper.py#keep_me resolves, '
        'scripts/real_helper.py#moved_away does not, gone_file.py#keep_me points at nothing."""\n'
        "def test_placeholder():\n    assert True\n", encoding="utf-8")

    cites = prose_symbol_citations(tmp_path)
    assert [c["symbol"] for c in cites] == ["keep_me", "moved_away", "keep_me"], cites
    offenders = unresolved_prose_symbol_citations(tmp_path)
    assert {o["symbol"] for o in offenders} == {"moved_away", "keep_me"}, offenders
    assert {o["why"] for o in offenders} == {"SYMBOL_NOT_IN_TARGET", "FILE_ABSENT"}, offenders
    assert offenders[0]["from"].startswith("tests/t_prose.py"), offenders


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
    work_source = source_roots.work_root()
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
