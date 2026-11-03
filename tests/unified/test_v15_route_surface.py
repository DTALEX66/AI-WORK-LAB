# SPDX-License-Identifier: MIT
"""V15 (audit F1): the whole HTTP surface is enumerated, registered and guarded.

What this file closes, stated precisely:

* **the compat surface had no test at all.** The 89 DESIGN-LAB compatibility
  routes (``domains.design.design_lab.http_service.ROUTES``, prefix ``/api/``)
  were probed live once and written into ``migration/route-surface.csv``, but no
  pytest file referenced a single one of them: ``tests/unified`` only ever asked
  ``/api/v1/*`` and ``/api/work/*``. ``scripts/boot_probe.py`` carried the
  sentence "401 without a token (kernel guard still applies on the compat
  surface)" in its docstring while its executed check list probed 401 on
  ``/api/v1/health`` only -- narrative, not evidence.
* **``COMPATIBILITY_MAP`` was only ever read, never walked.** The 10 old WORK
  paths in ``backend/core/work_surfaces.py`` had 2 of their *values* asserted
  anywhere in the suite (``test_v11_audit_rework.py`` pins
  ``["/api/v1/snapshot"]`` and prints the map). A value pointing at an
  unregistered or crashing target would have passed.

So the assertions below are: (1) the register's population is exactly the two
live route tables re-enumerated from imports -- a route added later without a
register row fails, and so does a register row for a route that is not mounted;
(2) the register's verdict/status vocabulary is closed and every row carries a
status and a reason, with defects named rather than counted; (3) the kernel
guard is executed on **every** compat ``GET`` route, covering every distinct
route shape, for all three legs (no token -> 401, wrong ``Host`` -> 403, valid
token -> reaches the handler and never 5xx unless the route is a registered
defect); (4) every ``COMPATIBILITY_MAP`` value is resolved against the mounted
tables and probed, with the walked count pinned to ``len(COMPATIBILITY_MAP)`` as
read at runtime; and (5) two falsification tests that break legs (3) and (4) on
purpose and require the checkers to report red -- a guard that cannot fail
guards nothing.

Counts are derived from the imports, never typed in: 75 / 49 / 89 / 164 appear
nowhere in this file as expected values.
"""
from __future__ import annotations

import csv
import importlib.util
import inspect
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

TARGET_ROOT = Path(__file__).resolve().parents[2]
for _entry in (str(TARGET_ROOT), str(TARGET_ROOT / "domains" / "design")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from backend.core.work_surfaces import COMPATIBILITY_MAP, WORK_SURFACE_ROUTES  # noqa: E402
from backend.v1 import V1_ROUTES  # noqa: E402
try:
    from domains.design.design_lab import http_service as hs  # noqa: E402
except ImportError:
    # an installed wheel exposes design_lab as a top-level package; the route table is the
    # same object either way, and collection must not abort in that layout
    from design_lab import http_service as hs  # noqa: E402

REGISTER_CSV = TARGET_ROOT / "migration" / "route-surface.csv"
BOOT_PROBE = TARGET_ROOT / "scripts" / "boot_probe.py"

#: The three source labels the register is allowed to use, verbatim.
SOURCE_V1 = "backend.v1.V1_ROUTES"
SOURCE_WORK = "backend.core.work_surfaces.WORK_SURFACE_ROUTES (经 backend.v1.V1_ROUTES 装载)"
SOURCE_COMPAT = "domains.design.design_lab.http_service.ROUTES"
ALLOWED_SOURCES = {SOURCE_V1, SOURCE_WORK, SOURCE_COMPAT}

COL_SOURCE = "路由表来源"
COL_METHOD = "方法"
COL_PATTERN = "路径模式"
COL_PATH = "具体探测路径"
COL_STATUS = "HTTP状态"
COL_VERDICT = "判定"
COL_ERROR = "错误码"
COL_DEFECT = "缺陷"
COL_NOTE = "备注"

VERDICTS = {"成功", "领域拒绝", "缺陷"}
DEFECT_FLAGS = {"是", "否"}
VERDICT_CLASS = {"成功": "2xx", "领域拒绝": "4xx", "缺陷": "5xx"}
#: The status codes a row may be registered with. Anything outside this set is a
#: new vocabulary term and must be added here deliberately, with a reason.
STATUS_VOCABULARY = frozenset({200, 201, 204, 400, 404, 405, 409, 413, 415, 422, 503})

#: A path carrying a service-produced id is workspace-dependent: the register was
#: probed against its own seed workspace, this suite runs against a fresh temp
#: workspace, so only *id-free* rows can be compared verdict-class by verdict-class.
ID_IN_PATH = re.compile(r"[0-9a-f]{16,}")
PLACEHOLDER = re.compile(r"<[a-z_]+>")
#: A response is "typed" when it says what kind of answer it is. Every map target
#: carries one of these; the one that does not is pinned by exact shape instead
#: (see ``SUBJECT_ONLY_SHAPES``), so the rule is not loosened to accommodate it.
TYPE_MARKERS = ("status", "error", "code", "reason_code", "schema_version", "schemaVersion")
SUBJECT_ONLY_SHAPES = {"/api/work/control/receipts/f1-compat-task": ("task_id", "receipts")}


def _class(status) -> str:
    return "%dxx" % (int(status) // 100)


def live_index() -> dict:
    """(source, method, pattern) -> Route, read from the live tables only.

    ``V1_ROUTES`` is ``table + WORK_SURFACE_ROUTES``, so the work rows are split
    out by identity rather than by a second count, and the compat table is kept
    separate because it is mounted through ``extra_routes``.
    """
    v1, work, compat = list(V1_ROUTES), list(WORK_SURFACE_ROUTES), list(hs.ROUTES)
    work_keys = {(r.method, r.pattern) for r in work}
    index: dict = {}
    for route in v1:
        label = SOURCE_WORK if (route.method, route.pattern) in work_keys else SOURCE_V1
        index[(label, route.method, route.pattern)] = route
    for route in compat:
        index[(SOURCE_COMPAT, route.method, route.pattern)] = route
    assert len(index) == len(v1) + len(compat), (
        "the two tables overlap or repeat a row, so the enumeration is not a set")
    return index


@pytest.fixture(scope="module")
def register() -> list[dict]:
    assert REGISTER_CSV.is_file(), (
        "%s is missing: the live surface register is the thing under test here, "
        "regenerate it with scripts/probe_full_surface.py rather than skipping" % REGISTER_CSV)
    with REGISTER_CSV.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows, "%s parsed empty" % REGISTER_CSV
    return rows


def compat_get_plan(index: dict, register: list) -> list[dict]:
    """Every compat ``GET`` route **as the mounted table holds it**, with its row.

    The route list is taken from ``hs.ROUTES``, not from the CSV: deleting a
    register row therefore cannot shrink the sweep, it makes the lookup below
    fail with the reason. That is the difference between a test that reads the
    register and a test that enforces it.
    """
    by_key = {(row[COL_SOURCE], row[COL_METHOD], row[COL_PATTERN]): row for row in register}
    plan = []
    for route in hs.ROUTES:
        if route.method != "GET":
            continue
        key = (SOURCE_COMPAT, route.method, route.pattern)
        assert key in by_key, (
            "live compat route %s has no register row, so its declared status is unknown" % (key,))
        plan.append({"key": key, "row": by_key[key], "route": route,
                     "path": by_key[key][COL_PATH]})
    assert plan, "the compat table exposes no GET route at all -- re-read the source"
    return plan


def shape_of(route) -> str:
    """The route's dispatch shape: how it is matched and how many groups it binds.

    Four independent axes the kernel actually treats differently
    (``http_service.dispatch``): exact vs regex, whole target vs path-only,
    number of capture groups, and whether the pattern can match two different
    targets (an optional branch).
    """
    groups = re.compile(route.pattern).groups
    return "match=%s target=%s groups=%d optional=%s" % (
        "exact" if route.exact else "regex",
        "path_only" if route.path_only else "full_target",
        groups,
        "yes" if "(?" in route.pattern else "no")


def collect_legs(client, plan: list[dict], *, anonymous_leg_sends_token: bool = False,
                 authenticated_leg_loses_token: bool = False) -> list[dict]:
    """The three real HTTP legs per route. The two keyword flags exist only so
    the falsification test can break one leg and prove the checker notices."""
    legs = []
    for item in plan:
        path = item["path"]
        legs.append({
            "key": item["key"],
            "path": path,
            "row": item["row"],
            "anonymous": client.get(path, token=(
                client.token if anonymous_leg_sends_token else None)),
            "wrong_host": client.get(path, host="localhost:%d" % client.port),
            "authenticated": client.get(path, token=(
                None if authenticated_leg_loses_token else client.token)),
        })
    return legs


def guard_failures(legs: list[dict], declared_defects: set) -> tuple[list[str], set]:
    """Pure verdict over collected legs, so it can be fed a broken set on purpose.

    ``declared_defects`` is the register's own defect set for the probed routes:
    a 5xx is only tolerated on a row the register already names as a defect, and
    such a row must still 5xx (a fix has to be deliberate, see the test below).
    """
    failures: list[str] = []
    live_defects: set = set()
    for leg in legs:
        where = "%s %s" % (leg["key"][1], leg["path"])
        anon_status, anon_body = leg["anonymous"]
        if anon_status != 401 or anon_body.get("error") != "UNAUTHORIZED":
            failures.append("%s: no-token leg returned %s %s, expected 401 UNAUTHORIZED"
                            % (where, anon_status, anon_body))
        host_status, host_body = leg["wrong_host"]
        if host_status != 403 or host_body.get("error") != "HOST_DENIED":
            failures.append("%s: wrong-Host leg returned %s %s, expected 403 HOST_DENIED"
                            % (where, host_status, host_body))
        auth_status, auth_body = leg["authenticated"]
        if auth_status in (401, 403):
            failures.append("%s: the bearer token never reached the compat handler (%s %s)"
                            % (where, auth_status, auth_body))
        if auth_status >= 500:
            if leg["key"] not in declared_defects:
                failures.append("%s: unregistered 5xx %s %s -- add it to the register as a "
                                "named defect, do not absorb it here"
                                % (where, auth_status, auth_body))
            else:
                live_defects.add(leg["key"])
        if not ID_IN_PATH.search(leg["path"]):
            expected_class = VERDICT_CLASS[leg["row"][COL_VERDICT]]
            if _class(auth_status) != expected_class:
                failures.append("%s: id-free route answered %s (%s) but the register classes "
                                "it as %s / %s" % (where, auth_status, auth_body,
                                                   leg["row"][COL_VERDICT], expected_class))
    return failures, live_defects


def map_report(client, mapping: dict, index: dict) -> dict:
    """Walk every COMPATIBILITY_MAP entry: resolve its value, then probe it.

    Returns ``walked`` (the old paths actually iterated), ``probed`` (entries
    that got a real HTTP answer) and ``failures``.
    """
    failures: list[str] = []
    walked: list[str] = []
    probed = 0
    for old_path, value in mapping.items():
        walked.append(old_path)
        head = str(value).split(" (")[0].strip()
        parts = urlsplit(head)
        target_path = PLACEHOLDER.sub("f1-compat-task", parts.path)
        query = re.sub(r"\bN\b", "2", parts.query)
        probe_target = target_path + (("?" + query) if query else "")
        mounted = [route for route in index.values()
                   if route.pattern == target_path
                   or (not route.exact and re.fullmatch(route.pattern, target_path))]
        if not mounted:
            failures.append("%s -> %r is not a registered route on this kernel" %
                            (old_path, value))
            continue
        methods = sorted({route.method for route in mounted})
        if "GET" in methods:
            status, body = client.get(probe_target)
        elif "POST" in methods:
            # /api/control/operations was a write entry; the unified mount serves
            # it as POST only, so a GET there is a 404 for the wrong reason.
            status, body = client.post(probe_target, {})
        else:
            failures.append("%s -> %s is mounted but not for any readable method %s"
                            % (old_path, target_path, methods))
            continue
        probed += 1
        if status in (401, 403):
            failures.append("%s -> %s: the guard answered instead of the target (%s)"
                            % (old_path, target_path, body))
        if status >= 500:
            failures.append("%s -> %s: target answered 5xx %s %s -- a compatibility value "
                            "must not point at a crashing handler"
                            % (old_path, target_path, status, body))
        exact_shape = SUBJECT_ONLY_SHAPES.get(target_path)
        if exact_shape is not None:
            if tuple(sorted(body)) != tuple(sorted(exact_shape)) or body.get("task_id") != \
                    target_path.rsplit("/", 1)[-1]:
                failures.append("%s -> %s: expected exactly %s echoing the subject, got %s"
                                % (old_path, target_path, exact_shape, body))
        elif "raw" in body:
            if "event:" not in body["raw"] or "data:" not in body["raw"]:
                failures.append("%s -> %s: SSE target did not emit frames: %r"
                                % (old_path, target_path, body["raw"][:120]))
            elif query and body["raw"].count("event:") != int(query.split("=")[1]):
                failures.append("%s -> %s: asked for %s frames, got %d"
                                % (old_path, target_path, query, body["raw"].count("event:")))
        elif not any(marker in body for marker in TYPE_MARKERS):
            failures.append("%s -> %s: %s carries no typed status (%s)"
                            % (old_path, target_path, body, TYPE_MARKERS))
    return {"walked": walked, "probed": probed, "failures": failures}


def load_boot_probe():
    spec = importlib.util.spec_from_file_location("f1_boot_probe_module", str(BOOT_PROBE))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- 1
def test_register_population_is_exactly_the_live_route_tables(register):
    index = live_index()
    v1, work, compat = list(V1_ROUTES), list(WORK_SURFACE_ROUTES), list(hs.ROUTES)

    listed = [(row[COL_SOURCE], row[COL_METHOD], row[COL_PATTERN]) for row in register]
    sources = {row[COL_SOURCE] for row in register}
    assert sources <= ALLOWED_SOURCES, "unknown 路由表来源 label(s): %s" % (sources - ALLOWED_SOURCES)
    assert len(listed) == len(set(listed)), "the register lists one route more than once"

    # Both directions, as one set equation: a route without a row and a row
    # without a route each fail here.
    missing = sorted(set(index) - set(listed))
    unmounted = sorted(set(listed) - set(index))
    assert not missing, "%d live route(s) have no register row: %s" % (len(missing), missing[:5])
    assert not unmounted, "%d register row(s) name no mounted route: %s" % (
        len(unmounted), unmounted[:5])

    # Every count derived, none typed in.
    by_source = {}
    for row in register:
        by_source[row[COL_SOURCE]] = by_source.get(row[COL_SOURCE], 0) + 1
    assert by_source[SOURCE_COMPAT] == len(compat), by_source
    assert by_source[SOURCE_WORK] == len(work), by_source
    assert by_source[SOURCE_V1] == len(v1) - len(work), by_source
    assert len(register) == len(v1) + len(compat)
    assert len(v1) == len(work) + by_source[SOURCE_V1]


# --------------------------------------------------------------------------- 2
def test_register_verdict_and_status_vocabulary_is_closed(register):
    for row in register:
        where = "%s %s" % (row[COL_METHOD], row[COL_PATTERN])
        assert row[COL_VERDICT] in VERDICTS, "%s: 判定 %r is outside %s" % (
            where, row[COL_VERDICT], sorted(VERDICTS))
        assert row[COL_DEFECT] in DEFECT_FLAGS, "%s: 缺陷 %r is not 是/否" % (where, row[COL_DEFECT])
        status = str(row[COL_STATUS]).strip()
        assert status, "%s: row with no HTTP状态" % where
        assert status.isdigit(), "%s: HTTP状态 %r is not a bare code" % (where, status)
        code = int(status)
        assert code in STATUS_VOCABULARY, "%s: status %s is not in the closed vocabulary" % (
            where, code)
        assert str(row[COL_NOTE] or "").strip(), "%s: row with no 备注 reason" % where
        assert _class(code) == VERDICT_CLASS[row[COL_VERDICT]], (
            "%s: %s/%s disagrees with status %s" % (where, row[COL_DEFECT],
                                                    row[COL_VERDICT], code))
        if row[COL_DEFECT] == "是":
            assert row[COL_VERDICT] == "缺陷", "%s: 缺陷=是 but 判定=%s" % (where, row[COL_VERDICT])
            assert str(row[COL_ERROR] or "").strip(), (
                "%s: a defect row must name its 错误码, never stand on the flag alone" % where)
        else:
            assert code < 500, "%s: 缺陷=否 on a 5xx hides a defect" % where
    defects = [row for row in register if row[COL_DEFECT] == "是"]
    assert all(row[COL_VERDICT] == "缺陷" for row in defects)
    assert len(defects) == len({(r[COL_SOURCE], r[COL_METHOD], r[COL_PATTERN]) for r in defects})


# --------------------------------------------------------------------------- 3
def test_compat_get_probe_plan_covers_every_route_and_every_shape(register):
    index = live_index()
    plan = compat_get_plan(index, register)
    wanted = {(SOURCE_COMPAT, route.method, route.pattern)
              for route in hs.ROUTES if route.method == "GET"}
    assert wanted, "the compat table exposes no GET route at all -- re-read the source"
    assert {item["key"] for item in plan} == wanted, (
        "the compat GET sweep is not the whole compat GET surface")
    probed_shapes = {shape_of(index[key]) for key in wanted}
    assert {shape_of(item["route"]) for item in plan} == probed_shapes
    assert len(probed_shapes) > 1, (
        "one shape for the whole compat surface means shape_of() has stopped discriminating")


def test_kernel_guard_holds_on_every_compat_route(server, register):
    """The headline: the kernel guard is executed on the compat surface, in full.

    Every compat ``GET`` route, three legs each, over real ``http.client`` to
    127.0.0.1: no token must be 401 UNAUTHORIZED, a foreign ``Host`` must be 403
    HOST_DENIED, and a valid token must reach the handler and come back without
    5xx. Only rows the register already names as defects may 5xx -- and they must
    still 5xx, so removing a defect row is a deliberate act, not a side effect.
    """
    index = live_index()
    plan = compat_get_plan(index, register)
    declared_defects = {item["key"] for item in plan if item["row"][COL_DEFECT] == "是"}
    legs = collect_legs(server.client, plan)
    failures, live_defects = guard_failures(legs, declared_defects)

    assert not failures, "%d contract violation(s) across %d compat GET routes:\n%s" % (
        len(failures), len(legs), "\n".join(failures[:15]))
    disappeared = sorted(declared_defects - live_defects)
    assert not disappeared, (
        "the register still lists %s as a defect but the live surface no longer fails there; "
        "re-run scripts/probe_full_surface.py and retire the row on purpose" % disappeared[:3])
    wanted = {(SOURCE_COMPAT, route.method, route.pattern)
              for route in hs.ROUTES if route.method == "GET"}
    assert len(legs) == len(plan) == len(wanted)


# --------------------------------------------------------------------------- 3b
#: ``dispatch()`` matches a route against the **raw** request target unless that route declares
#: ``path_only`` (``design_lab/http_service.py:592``). A handler that reads the query behind a
#: route without the flag is therefore unreachable code for every request carrying one: the query
#: is part of the string being compared and the comparison fails. That is cloud audit N02 on
#: ``GET /api/v1/tasks`` -- its handler had parsed ``project_id`` since it was written, and no
#: request with a filter had ever reached it. The flag is one boolean on one table row, and until
#: this section nothing compared that row with the body of the handler the row names.
#:
#: The compat table is deliberately not walked here: its handlers live on delegate objects built
#: inside ``build_server`` and its convention names the query inside the pattern
#: (``/api/projects/…/directions(?:\?after=…)?``), which is a different contract from the flag. Its
#: guard stays the live three-leg sweep below.
QUERY_READING = re.compile(r"parse_qsl\(|urlsplit\(handler\.path\)")


def _v1_namespace_texts() -> dict:
    """Source of every function in ``backend.v1``: module-level helpers and ``V1API`` methods.

    Helpers belong in the population because a handler that hands the request to ``_search`` or to
    ``_query_pairs`` reads the query through them; scanning only the 40 action bodies would leave
    ``/api/v1/knowledge/search`` and ``/api/v1/tasks`` unpinned.
    """
    import backend.v1 as v1_module
    from types import FunctionType
    texts = {name: inspect.getsource(value)
             for name, value in vars(v1_module).items()
             if isinstance(value, FunctionType) and value.__module__ == v1_module.__name__}
    texts.update({name: inspect.getsource(value)
                  for name, value in vars(v1_module.V1API).items()
                  if isinstance(value, FunctionType)})
    return texts


def query_reading_names(texts=None) -> set:
    """Every name that reads the query, directly or through any number of in-module hops."""
    texts = _v1_namespace_texts() if texts is None else texts
    found = {name for name, text in texts.items() if QUERY_READING.search(text)}
    for _ in range(len(texts) + 1):
        added = {name for name, text in texts.items()
                 if name not in found and any(
                     re.search(r"(?:self\.)?%s\s*\(" % re.escape(reader), text)
                     for reader in found)}
        if not added:
            return found
        found |= added
    return found


def routes_reaching_the_query_without_the_flag(table) -> list:
    readers = query_reading_names()
    return ["%s %s -> %s" % (route.method, route.pattern, route.action)
            for route in table if route.action in readers and not route.path_only]


def test_every_backend_route_whose_handler_reads_the_query_declares_path_only():
    flagged = ["%s %s" % (route.method, route.pattern)
               for route in V1_ROUTES if route.action in query_reading_names() and route.path_only]
    offenders = routes_reaching_the_query_without_the_flag(V1_ROUTES)
    assert query_reading_names(), (
        "no function in backend.v1 reads a query -- the pattern has stopped matching the real "
        "code and the assertion below would be vacuously green")
    assert "GET /api/v1/tasks" in flagged, (
        "the task list is the route N02 was about; losing it from the population means the "
        "guard stopped seeing its handler, not that the defect went away")
    assert offenders == [], (
        "these handlers can only be reached by a request without a query, yet they parse one: %s"
        % offenders)


def test_falsification_removing_the_flag_names_the_route_it_blinds():
    """The guard above must be able to fail: flip the one boolean on one row and it has to say so.

    The copy is a fresh ``Route`` object, never a mutation of the mounted table -- the mounted
    table is the control, so a plant that reports on both proves nothing.
    """
    blind = [hs.Route(route.method, route.pattern, route.action,
                      exact=route.exact, path_only=False, when=route.when)
             if route.pattern == "/api/v1/tasks" and route.action == "_v1_list_tasks" else route
             for route in V1_ROUTES]
    named = routes_reaching_the_query_without_the_flag(blind)
    assert named == ["GET /api/v1/tasks -> _v1_list_tasks"], named
    assert routes_reaching_the_query_without_the_flag(V1_ROUTES) == [], (
        "the mounted table is the control for this plant; if it also reports the defect the "
        "plant proves nothing")


# --------------------------------------------------------------------------- 4
def test_compatibility_map_is_walked_in_full_at_runtime():
    """The loop over the map cannot silently shrink: it iterates what the module holds."""
    entries = list(COMPATIBILITY_MAP.items())
    assert len(entries) == len(COMPATIBILITY_MAP)
    assert len(entries) > 1, (
        "a one-entry map would make every value assertion below vacuous")
    keys = [old for old, _value in entries]
    assert len(set(keys)) == len(keys), "duplicate old path in COMPATIBILITY_MAP"
    for old, value in entries:
        assert str(value).startswith("/"), "%s -> %r is not an HTTP path" % (old, value)
        assert old != value, "%s maps to itself; the compat row is meaningless" % old


def test_every_compatibility_map_value_is_mounted_and_answers(server):
    """Probe all 10 values, not the 2 that test_v11 pinned.

    Each value must resolve to a route actually mounted on this kernel and answer
    with a typed, non-5xx status; an unregistered or crashing target fails here.
    """
    index = live_index()
    report = map_report(server.client, COMPATIBILITY_MAP, index)
    assert sorted(report["walked"]) == sorted(COMPATIBILITY_MAP), report["walked"]
    assert report["probed"] == len(COMPATIBILITY_MAP), (
        "walked %s entries but only probed %d" % (len(COMPATIBILITY_MAP), report["probed"]))
    assert not report["failures"], "COMPATIBILITY_MAP targets failed:\n%s" % "\n".join(
        report["failures"])


# --------------------------------------------------------------------- 5 falsify
def test_falsification_guard_checker_goes_red_when_a_leg_is_broken(server, register):
    """A guard that cannot fail guards nothing: break one leg, require red."""
    index = live_index()
    plan = [item for item in compat_get_plan(index, register)
            if item["row"][COL_DEFECT] != "是"][:1]
    assert plan, "no clean compat GET row available to falsify against"
    declared = {item["key"] for item in plan if item["row"][COL_DEFECT] == "是"}

    honest = collect_legs(server.client, plan)
    assert guard_failures(honest, declared)[0] == [], (
        "the sweep reports red on a route that is behaving: the falsification below proves "
        "nothing until this leg is clean")

    # The authenticated leg is sent with the token stripped -- the exact mistake
    # a future edit to collect_legs() would make. It must be caught.
    broken = collect_legs(server.client, plan, authenticated_leg_loses_token=True)
    failures, _ = guard_failures(broken, declared)
    assert failures, "stripping the token from the authenticated leg went unnoticed"

    # And the anonymous leg silently carrying a token: 401 is the point.
    inverted = collect_legs(server.client, plan, anonymous_leg_sends_token=True)
    assert guard_failures(inverted, declared)[0], (
        "a no-token leg that actually sends the token went unnoticed")


def test_falsification_map_checker_goes_red_on_an_unmounted_target():
    """Point one value at a path that is not mounted; the walker must say so."""
    index = live_index()
    good = dict(COMPATIBILITY_MAP)
    broken = dict(COMPATIBILITY_MAP)
    first = next(iter(broken))
    broken[first] = "/api/work/observer/definitely-not-mounted"

    class _NullClient:
        port = 1

        def get(self, path, **_kwargs):
            return 404, {"error": "NOT_FOUND"}

        def post(self, path, body=None, **_kwargs):
            return 404, {"error": "NOT_FOUND"}

    client = _NullClient()
    unmounted = map_report(client, broken, index)
    assert unmounted["failures"], "an unregistered COMPATIBILITY_MAP target passed silently"
    # Same client, same code path, real map: the only extra complaint is the one
    # injection introduced, so the failure is attributed and not incidental.
    baseline = map_report(client, good, index)["failures"]
    extra = [line for line in unmounted["failures"] if line not in baseline]
    assert len(extra) == 1 and first in extra[0], (baseline, unmounted["failures"])


# --------------------------------------------------------------------- boot probe
def test_boot_probe_executes_the_compat_guard_it_documents():
    """The docstring/execution mismatch that started this, pinned as a test.

    ``scripts/boot_probe.py`` used to claim a compat-surface 401 check that its
    check list never ran. Its checks and expectations are module-level data now,
    so this reads them instead of re-reading its prose.
    """
    module = load_boot_probe()
    checks = list(module.CHECKS)
    names = [name for name, _m, _p, _a in checks]
    assert len(names) == len(set(names)), "duplicate check name in CHECKS"
    assert set(module.EXPECTED) == set(names), (
        "a check without a declared expectation, or an expectation for a check that is not run")

    compat_checks = [c for c in checks if c[2].startswith("/api/")
                     and not c[2].startswith("/api/v1/") and not c[2].startswith("/api/work/")]
    assert compat_checks, "boot_probe runs no compat-surface check at all"
    anonymous_compat = [c for c in compat_checks if c[3] is False]
    assert anonymous_compat, (
        "boot_probe still does not run the compat-surface no-token guard it documents")
    for name, _method, _path, _auth in anonymous_compat:
        assert module.EXPECTED[name] == 401, name
    assert any(module.EXPECTED[name] == 200 for name, _m, _p, auth in compat_checks
               if auth), "no authenticated compat GET is expected to answer"
    assert any(module.EXPECTED[name] == 403 for name in module.EXPECTED), (
        "the compat Host pin is asserted nowhere in the boot probe")

    # The legacy checks the script already had are still there, unchanged.
    for legacy in ("v1_health", "design_compat_health", "design_compat_capabilities",
                   "design_compat_knowledge_search", "workbench_shell", "v1_health_no_token"):
        assert legacy in names, "%s was dropped from CHECKS" % legacy

    source = BOOT_PROBE.read_text(encoding="utf-8")
    assert "ensure_ascii=True" in source, (
        "the printed summary must be ascii-safe: the console is cp936")
    assert "ensure_ascii=False" not in source, source

    # And the guard the docstring claims is really in the executed list, by path.
    documented = module.__doc__ or ""
    if "compat surface" in documented:
        assert any(path.startswith("/api/") and not path.startswith("/api/v1")
                   for _n, _m, path, auth in checks if auth is False), documented
