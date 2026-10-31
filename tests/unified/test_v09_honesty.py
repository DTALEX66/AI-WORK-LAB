# SPDX-License-Identifier: MIT
"""V09: unavailable executors, hosts and deferred capabilities answer honest
states; a simulated connection success cannot mint real qualification."""
from __future__ import annotations

import json

from backend.core.qualifications import probe_record


def _connection_rows(server) -> dict:
    status, body = server.client.get("/api/v1/connections")
    assert status == 200, body
    assert body["connections"]
    return {row["connection_id"]: row for row in body["connections"]}


def test_connections_never_claim_connected_without_a_probe(server):
    """The falsifiable version of the old same-source check.

    What used to sit here compared the route's hard-coded list against the string
    ``"CONNECTED"`` — a constant checked against a constant, so the assertion could
    never fail (audit category (c)).  The route now reads the qualification ledger,
    which means this test can move the ledger and watch the answer move with it.
    Every step below is a state the endpoint did not already know.
    """
    ledger = server.qualifications
    snapshot = (ledger.path.read_text(encoding="utf-8")
                if ledger.path.is_file() else json.dumps({"records": []}))
    version = server.api.candidate()
    # timestamps are second-resolution and ``latest_for`` picks the newest, so each
    # fixture step is stamped later than the one before it and the outcome never
    # depends on how long the test takes to run.
    stamps = iter(["2099-01-01T00:00:0" + str(step) + "+00:00" for step in range(1, 9)])

    def append(*, origin="live", connection="CONNECTED", digest=None, expires=None,
               outcome="VERIFIED"):
        row = probe_record(capability_id="work.executors", operation="executor.invoke",
                           scope="local_read", subject="work adapter registry",
                           version={"digest": digest or version["digest"],
                                    "files": version["files"]},
                           outcome=outcome, evidence_refs=["probe:work.executors/falsifier"],
                           detail="falsifier fixture written by test_v09",
                           data_origin=origin, connection=connection, ttl_seconds=900)
        row["observed_at"] = next(stamps)
        row["expires_at"] = expires or "2099-12-31T00:00:00+00:00"
        ledger.append(row)
        return row

    def restore():
        ledger.path.write_text(snapshot, encoding="utf-8", newline="\n")

    # 0. baseline — nothing in this build records a connection, so the ledger's
    #    silence is reported as NOT_PROBED with a reason, never as a green default.
    baseline = _connection_rows(server)["work-adapters"]
    assert baseline["state"] == "NOT_PROBED", baseline
    assert baseline["evidence"] is None
    assert baseline["unavailable_reasons"], baseline
    # the deleted literal must not come back through any other door
    for row in _connection_rows(server).values():
        assert row["state"] != "CONNECTED_LOCAL", row
    assert set(_connection_rows(server)) == {"design-native-hosts", "design-comfy",
                                             "work-adapters"}

    # 1. a live record bound to THIS candidate that observed a connection flips it
    append()
    moved = _connection_rows(server)["work-adapters"]
    assert moved["state"] == "CONNECTED", moved
    assert moved["qualification"] == "VERIFIED", moved
    assert moved["evidence"]["candidate_digest"] == version["digest"], moved
    assert moved["evidence"]["data_origin"] == "live", moved
    # the other axes stay separate: a connection does not launder a PARTIAL
    # implementation or a NOT_GRANTED authorization into readiness
    assert any("implementation=PARTIAL" in reason for reason in moved["unavailable_reasons"]), moved
    assert any("authorization=NOT_GRANTED" in reason
               for reason in moved["unavailable_reasons"]), moved
    assert not any("qualification=" in reason for reason in moved["unavailable_reasons"]), moved

    # 2. the same claim from a synthetic probe does not earn it
    append(origin="test")
    synthetic = _connection_rows(server)["work-adapters"]
    assert synthetic["state"] == "NOT_PROBED", synthetic
    assert any("data_origin" in reason or "synthetic" in reason
               for reason in synthetic["unavailable_reasons"]), synthetic

    # 3. nor does a record written against a different candidate
    append(origin="live", digest="f" * 64)
    foreign = _connection_rows(server)["work-adapters"]
    assert foreign["state"] == "NOT_PROBED", foreign
    assert foreign["qualification"] == "EXPIRED", foreign
    assert any("candidate" in reason for reason in foreign["unavailable_reasons"]), foreign

    # 4. nor one whose freshness window has passed
    append(expires="2020-01-01T00:00:00+00:00")
    stale = _connection_rows(server)["work-adapters"]
    assert stale["state"] == "NOT_PROBED", stale
    assert any("freshness window" in reason for reason in stale["unavailable_reasons"]), stale

    # 5. a FAILED observation is not a connection either
    append(outcome="FAILED")
    failed = _connection_rows(server)["work-adapters"]
    assert failed["state"] == "NOT_PROBED", failed
    assert failed["qualification"] == "FAILED", failed

    # 6. take the records away and the surface goes back to NOT_PROBED by itself
    restore()
    reverted = _connection_rows(server)["work-adapters"]
    assert reverted["state"] == "NOT_PROBED", reverted
    assert reverted["evidence"] is None, reverted
    assert reverted["unavailable_reasons"], reverted

    # 7. and there is still no route that writes a connection from the client side
    status, body = server.client.post("/api/v1/connections", {"state": "CONNECTED"})
    assert status == 404  # no such route exists
    assert _connection_rows(server)["work-adapters"]["state"] == "NOT_PROBED"


def test_tool_state_names_the_record_that_produced_it(server):
    """Every tool row is traceable: a value is either a record's own connection
    axis or NOT_PROBED with the reason the ledger is silent."""
    status, body = server.client.get("/api/v1/tools")
    assert status == 200, body
    version = server.api.candidate()["digest"]
    records = server.qualifications.records()
    for row in body["tools"]:
        assert row["state"] != "CONNECTED_LOCAL", row
        assert row["state"] in ("NOT_REQUIRED", "CONNECTED", "NOT_PROBED", "DISCONNECTED"), row
        candidates = [record for record in records
                      if record.get("capability_id") == row["bound_capability"]
                      and record.get("operation") == row["operation"]]
        if row["state"] == "NOT_PROBED":
            assert row["unavailable_reasons"], row
            continue
        assert row["evidence"], row
        assert row["evidence"]["candidate_digest"] == version, row
        assert row["evidence"]["data_origin"] == "live", row
        assert any(record.get("connection") == row["state"] for record in candidates), row
    assert body["state_rule"]


def test_unavailable_capabilities_carry_reasons(server):
    status, body = server.client.get("/api/v1/capabilities")
    assert status == 200
    for capability in body["capabilities"]:
        if capability["can_invoke"] is False:
            assert capability["unavailable_reasons"], capability["capability_id"]
        if capability["implementation"] == "DEFERRED":
            assert capability["phase"].startswith("P"), capability["capability_id"]


def test_improvements_answer_contract_only(server):
    status, body = server.client.get("/api/v1/improvements")
    assert status == 200
    assert body["status"] == "CONTRACT_ONLY"
    assert body["activation_state"] == "UNAVAILABLE"


def test_demo_data_origin_cannot_grant_live_qualification(server):
    status, project = server.client.post("/api/v1/projects", {"name": "d", "source": "design"})
    assert status == 201
    # a task created with demo origin is stored as demo…
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "design", "title": "演示任务",
        "acceptance": {"data_origin": "demo"}})
    assert status == 201
    assert task["data_origin"] == "demo"
    # …and the capability catalog still reports live entries only — a demo task
    # record never appears as a live qualification anywhere
    status, caps = server.client.get("/api/v1/capabilities")
    for capability in caps["capabilities"]:
        assert capability["data_origin"] == "live"


# ---------------------------------------------------------------------------
# 登记行 05#L16|radar —「信息来源、日期、探测与资格有区别」
# (domains/design/design_lab/model_catalog.py:97 `def catalog()`).
#
# 以下节点是新追加的，不改动上面任何既有节点。它们不走 HTTP 路由，直接调 `catalog()` 本身，
# 并现读它真正打开的那两份台账（`model_radar.REGISTRY_PATH` 与 `model_catalog.PROVIDERS_PATH`，
# 都由 domains/design/design_lab/runtime/state_resources.py:100 `repo_resource()` 解析：先取
# packaged 副本，所以下面比的是被读到的字节，不是照抄登记里的数字）。
# ---------------------------------------------------------------------------

import hashlib  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from design_lab import model_catalog  # noqa: E402
from design_lab.readiness import ReadinessError, model_radar  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

#: a key that would read as "this row carries its own date"
_DATE_KEY = re.compile(r'(?i)(date|observed|timestamp|_at\b)')

_SYNTHETIC_MODEL_ID = 'v09-radar-fixture-model'
_FIXTURE_LOCAL = 'model-library:v09/fixture.safetensors'


def _keys_with_dates(document):
    return [key for key in document if _DATE_KEY.search(key)]


def _entry(**overrides):
    """One minimal legal radar entry: a recorded candidate, nothing loaded or run."""
    entry = {
        'model_id': _SYNTHETIC_MODEL_ID,
        'family': 'image-generation',
        'source': {'kind': 'huggingface', 'ref': f'huggingface/{_SYNTHETIC_MODEL_ID}',
                   'license_id': 'MIT'},
        'radar_state': 'WATCH',
        'machine_state': 'ABSENT',
        'local_path': None,
        'weights_sha256': [],
        'hash_source': None,
        'hardware_fit': {'vram_gib_required': None, 'verdict': 'UNKNOWN'},
        'default_enabled': False,
        'qualified_by': None,
        'blocking_reason': None,
        'evidence_ref': None,
        'rights': {'license_id': 'MIT', 'territory_limits': [], 'commercial_use': 'UNKNOWN'},
        'notes': 'synthetic fixture written by test_v09; nothing was downloaded, loaded or run.',
    }
    entry.update(overrides)
    return entry


def _registry(entries, *, observed_at='2026-01-01T00:00:00+00:00'):
    return {
        'schema_version': model_radar.SCHEMA_VERSION,
        'task_id': model_radar.TASK_ID,
        'observed_at': observed_at,
        'inventory_ref': model_radar.INVENTORY_REF,
        'external_assets_ref': model_radar.EXTERNAL_ASSETS_REF,
        'policy': ['synthetic fixture: this registry records a candidate and loads nothing'],
        'hardware': {'available_vram_mib': 8151, 'gpu': 'fixture-gpu',
                     'source': 'synthetic, never probed by this test'},
        'entries': entries,
    }


def _write_json(path, document):
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def _catalog_from(monkeypatch, root, registry, providers):
    """Point the two read paths at throwaway files and take whatever catalog() answers."""
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / 'model-radar.json', registry)
    _write_json(root / 'provider-capabilities.json', providers)
    monkeypatch.setattr(model_radar, 'REGISTRY_PATH', root / 'model-radar.json')
    monkeypatch.setattr(model_catalog, 'PROVIDERS_PATH', root / 'provider-capabilities.json')
    return model_catalog.catalog()


def _diff_paths(left, right, prefix='$'):
    """Every JSON pointer where two documents differ, so "only what I changed" is checkable."""
    if isinstance(left, dict) and isinstance(right, dict):
        found = []
        for key in sorted(set(left) | set(right)):
            pointer = f'{prefix}.{key}'
            if key not in left or key not in right:
                found.append(pointer)
            else:
                found.extend(_diff_paths(left[key], right[key], pointer))
        return found
    if isinstance(left, list) and isinstance(right, list):
        found = []
        if len(left) != len(right):
            found.append(f'{prefix}[len]')
        for index, (a, b) in enumerate(zip(left, right)):
            found.extend(_diff_paths(a, b, f'{prefix}[{index}]'))
        return found
    return [] if left == right else [prefix]


def test_radar_catalog_source_date_probe_qualification_are_four_separate_axes():
    """登记行 05#L16|radar，验收原文「信息来源、日期、探测与资格有区别」。

    证明：`catalog()` 把四件事放在互不等价的键上——来源是行级 `source_ref`/`evidence_ref` 加
    文档级 `sources`，日期只有文档级 `observed_at`，探测是 `machine_state`，资格是
    `radar_state` + `default_enabled`。逐行核对：资格值只能取自 RADAR_STATES、探测值只能取自
    MACHINE_STATES，同一行里两个值永不相等（把 machine_state 顶进 radar_state 的合成改动会让
    本节点立刻红）。每行的布尔键恰是 {'default_enabled'}，说明代码没有再造第二个"看起来已就绪"
    的合并布尔；`weights_recorded` 是整数计数而不是布尔。台账 `notes` 写了 WEIGHTS_COMPLETE 的
    那些行，目录里 `weights_recorded` 仍为 0：文档写了不等于摘要登记过。资格轴还不许越界：
    任何 `default_enabled` 为 true 的行必须自己就是 QUALIFIED_LOCAL，两个计数都等于从台账现算
    的值。选择段保持"操作者自选、未执行、无发送通道"，`join.key` 仍是 null，两段台账没有被
    冒领成一张表。

    没证明：模型被加载、下载、哈希、运行过；许可被裁定过；`observed_at` 是这台机器此刻的真实
    观测时刻（它是台账里抄来的记录日期，本节点只验证它被如实带着走、没有下行成逐行日期——
    14 行共用一个文档级日期，行级日期不存在，这是登记验收里「日期」一轴的已知缺口）。
    """
    doc = model_catalog.catalog()
    registry = json.loads(model_radar.REGISTRY_PATH.read_text(encoding='utf-8'))
    entries = {row['model_id']: row for row in registry['entries']}
    rows = doc['models']

    assert set(entries) == {row['model_id'] for row in rows}
    for row in rows:
        assert {'source_ref', 'evidence_ref', 'machine_state', 'radar_state',
                'default_enabled'} <= set(row), row
        assert row['radar_state'] in model_radar.RADAR_STATES, row
        assert row['machine_state'] in model_radar.MACHINE_STATES, row
        # 探测与资格不是同一个值空间：谁也不能替谁说话
        assert row['radar_state'] != row['machine_state'], row
        # 没有第二个合并布尔（ready / verified 一类）被铸出来
        assert {key for key, value in row.items() if isinstance(value, bool)} \
            == {'default_enabled'}, row
        assert isinstance(row['weights_recorded'], int), row
        assert row['default_enabled'] is False or row['radar_state'] == 'QUALIFIED_LOCAL', row
        # 日期没有下行：行里不存在任何日期键，文档日期不被伪装成逐行观测时刻
        assert _keys_with_dates(row) == [], row
        source = entries[row['model_id']]
        assert row['weights_recorded'] == len(source.get('weights_sha256') or []), row
        if 'WEIGHTS_COMPLETE' in source.get('notes', ''):
            assert row['weights_recorded'] == 0, row

    assert doc['observed_at'] == registry['observed_at']
    assert _DATE_KEY.search('observed_at'), 'the catalogue lost its only date carrier'
    assert doc['counts']['qualified_local'] == sum(
        1 for row in entries.values() if row['radar_state'] == 'QUALIFIED_LOCAL'), doc['counts']
    assert doc['counts']['default_enabled_true'] == sum(
        1 for row in entries.values() if row['default_enabled'] is True), doc['counts']
    assert doc['counts']['default_enabled_true'] <= doc['counts']['qualified_local'], doc['counts']
    assert doc['join']['key'] is None, doc['join']
    assert doc['selection']['mode'] == 'USER_CHOSEN_NOT_LOCKED', doc['selection']
    assert doc['selection']['executed'] is False, doc['selection']
    assert doc['selection']['transport'] == 'NOT_CONNECTED', doc['selection']


def test_radar_catalog_absent_field_is_null_while_unknown_stays_unknown(monkeypatch, tmp_path):
    """登记行 05#L16|radar：未知与"没有这一项"不得塌成同一个值。

    证明：删掉 schema 允许省略的 `blocking_reason` / `evidence_ref` 之后，`catalog()` 对该行答
    的是显式 null（`is None`），不是 `''`、`0`、`False` 或 `True`；而台账真写了
    `verdict: "UNKNOWN"` 的行，目录里仍是字符串 `'UNKNOWN'`，与被删字段答出的 `None` 互不相等
    ——「记录过的未知」和「这一项不存在」是两种事实，目录把它们分开。`vram_gib_required: null`
    不被换算成 0。缺字段也不带来升格：该行资格仍是台账里的 WATCH，`default_enabled` 仍 false，
    `counts.default_enabled_true` 仍 0。删掉 schema 必填字段（`hardware_fit`）时目录直接拒绝加载，
    不会静默当成 null 或 0 渲染给选择面。

    已修（本轮之前这里是缺陷，本节点当时钉的是塌成同一个值的行为）：`weights_sha256` 被省略与被
    登记为空列表曾同时答 `weights_recorded: 0`，`_model()` 也不透传 `hash_source`/`qualified_by`。
    现在计数继续数它数得到的东西（0 = 确实没有摘要被登记），区别由 `weights_state` 三态承担
    （UNSTATED / REGISTERED_NONE / RECORDED），出处与判定人格子原样带出；文档级
    `counts.weights_unstated` / `weights_registered_none` 把两种"不知道"分别计数。
    「0 不被当成合格」这条不变量原样保留，另两个节点的折叠反证证明它能变红。

    没证明：合成夹具里的模型存在过或被探测过；真实台账逐行的缺失情况（这里用的是夹具）。
    """
    providers = json.loads(model_catalog.PROVIDERS_PATH.read_text(encoding='utf-8'))

    stripped = _entry()
    for gone in ('blocking_reason', 'evidence_ref'):
        stripped.pop(gone)
    documented_unknown = _entry(model_id='v09-radar-unknown-fixture',
                                source={'kind': 'huggingface', 'ref': 'huggingface/unknown-fixture',
                                        'license_id': 'MIT'})
    base = _catalog_from(monkeypatch, tmp_path / 'absent', _registry([stripped, documented_unknown]),
                         providers)
    absent_row, unknown_row = base['models']

    assert absent_row['blocking_reason'] is None, absent_row
    assert absent_row['evidence_ref'] is None, absent_row
    assert absent_row['vram_gib_required'] is None, absent_row
    assert unknown_row['hardware_fit'] == 'UNKNOWN', unknown_row
    # 两种事实、两个不同的值：塌成同一个就是本节点要抓的缺陷
    assert absent_row['blocking_reason'] != unknown_row['hardware_fit'], (absent_row, unknown_row)
    assert absent_row['radar_state'] == 'WATCH', absent_row
    assert absent_row['default_enabled'] is False, absent_row
    assert base['counts']['default_enabled_true'] == 0, base['counts']

    # 省略与空列表：计数都是 0（这确实是"没有摘要被登记"），但状态格把两者分开
    omitted_hashes = _entry(model_id='v09-radar-nohash-fixture',
                            source={'kind': 'huggingface', 'ref': 'huggingface/nohash-fixture',
                                    'license_id': 'MIT'})
    omitted_hashes.pop('weights_sha256')
    explicit_empty = _entry(model_id='v09-radar-emptyhash-fixture',
                            source={'kind': 'huggingface', 'ref': 'huggingface/emptyhash-fixture',
                                    'license_id': 'MIT'})
    two_rows = _catalog_from(monkeypatch, tmp_path / 'hashes',
                             _registry([omitted_hashes, explicit_empty]), providers)
    row_omitted, row_empty = two_rows['models']
    assert row_omitted['weights_recorded'] == 0, row_omitted
    assert row_empty['weights_recorded'] == 0, row_empty
    assert isinstance(row_omitted['weights_recorded'], int), row_omitted
    assert row_omitted['weights_recorded'] is not True, row_omitted
    assert two_rows['counts']['weights_recorded'] == 0, two_rows['counts']
    assert row_omitted['radar_state'] == 'WATCH', row_omitted
    assert row_empty['radar_state'] == 'WATCH', row_empty
    assert row_omitted['weights_state'] == 'UNSTATED', row_omitted
    assert row_empty['weights_state'] == 'REGISTERED_NONE', row_empty
    assert row_omitted['weights_state'] != row_empty['weights_state']
    assert two_rows['counts']['weights_unstated'] == 1, two_rows['counts']
    assert two_rows['counts']['weights_registered_none'] == 1, two_rows['counts']
    # 出处与判定人是台账里写的话：目录既不替它们编内容，也不把它们丢掉
    recorded = _entry(model_id='v09-radar-recorded-fixture',
                      source={'kind': 'huggingface', 'ref': 'huggingface/recorded-fixture',
                              'license_id': 'MIT'},
                      weights_sha256=['a' * 64],
                      hash_source='model hub manifest', qualified_by='owner 2026-10-20')
    one_recorded = _catalog_from(monkeypatch, tmp_path / 'recorded',
                                 _registry([recorded]), providers)
    assert one_recorded['models'][0]['weights_state'] == 'RECORDED', one_recorded['models'][0]
    assert one_recorded['models'][0]['weights_recorded'] == 1, one_recorded['models'][0]
    assert one_recorded['models'][0]['hash_source'] == 'model hub manifest'
    assert one_recorded['models'][0]['qualified_by'] == 'owner 2026-10-20'
    assert one_recorded['counts']['weights_recorded'] == 1, one_recorded['counts']
    assert one_recorded['counts']['weights_unstated'] == 0, one_recorded['counts']

    missing_required = _entry(model_id='v09-radar-nofit-fixture')
    missing_required.pop('hardware_fit')
    with pytest.raises(model_catalog.ModelCatalogError, match='refused to load'):
        _catalog_from(monkeypatch, tmp_path / 'nofit', _registry([missing_required]), providers)


def test_radar_catalog_source_and_date_equal_the_recorded_strings():
    """登记行 05#L16|radar：来源与日期可追溯，而且是字符串相等，不是"非空"这种弱断言。

    证明：`observed_at` 逐字符等于台账里的同一个字符串；`hardware.source`（机器事实的出处）与
    `policy` 也逐字符等于台账；每一行的 `source_ref` 等于该条自己的 `source.ref`、`evidence_ref`
    等于该条自己的值、`license_id`/`commercial_use` 等于该条 `rights` 里的值、`placement` 等于该条
    `source.kind`；每个端点行的 `source` 等于 provider 台账该行的 `source`，`evidence_level` 等于
    该行的 `evidence_level`。读到的字节与 `sources` 标签所指的仓根文档 sha256 相同。端点行没有任何
    日期键，provider 台账也没有 `observed_at`——目录没有替九行端点造日期。

    没证明：来源字符串指向的文件此刻在本机真的存在（`evidence_ref` 指向的 docs/ 路径、
    `source_ref` 的 model-library: 别名都没有被解析过）；日期是新鲜观测；许可被裁定；
    端点段的可追溯性完整——见下面两条被如实断言的现状：`sources.endpoints` 这个标签在仓根没有
    对应文件（真实字节只在 packaged 副本里），九行端点没有任何日期字段。要修复就把根文件补齐
    或把标签改成实际被读的路径，并给端点台账加日期轴，而不是让目录替它编一个。
    """
    doc = model_catalog.catalog()
    registry = json.loads(model_radar.REGISTRY_PATH.read_text(encoding='utf-8'))
    providers = json.loads(model_catalog.PROVIDERS_PATH.read_text(encoding='utf-8'))
    entries = {row['model_id']: row for row in registry['entries']}
    provider_rows = {row['provider_id']: row for row in providers['providers']}

    assert isinstance(doc['observed_at'], str)
    assert doc['observed_at'] == registry['observed_at']
    assert doc['hardware']['source'] == registry['hardware']['source']
    assert doc['policy'] == registry['policy']

    for row in doc['models']:
        source = entries[row['model_id']]
        assert row['source_ref'] == source['source']['ref'], row
        assert row['evidence_ref'] == source.get('evidence_ref'), row
        assert row['placement'] == source['source']['kind'], row
        assert row['license_id'] == source['rights']['license_id'], row
        assert row['commercial_use'] == source['rights']['commercial_use'], row
        assert _keys_with_dates(row) == [], row

    for row in doc['endpoints']:
        origin = provider_rows[row['provider_id']]
        assert row['source'] == origin['source'], row
        assert row['evidence_level'] == origin['evidence_level'], row
        assert _keys_with_dates(row) == [], row
    assert 'observed_at' not in providers, 'provider ledger gained a date the catalogue ignores'

    assert doc['sources']['models'] == 'design-lab/readiness/model-radar.json'
    assert doc['sources']['endpoints'] == 'design-lab/config/provider-capabilities.json'
    labelled_models = REPO_ROOT / 'design-lab' / 'readiness' / 'model-radar.json'
    labelled_endpoints = REPO_ROOT / 'design-lab' / 'config' / 'provider-capabilities.json'
    assert labelled_models.is_file(), labelled_models
    read_sha = hashlib.sha256(model_radar.REGISTRY_PATH.read_bytes()).hexdigest()
    label_sha = hashlib.sha256(labelled_models.read_bytes()).hexdigest()
    assert read_sha == label_sha, (str(model_radar.REGISTRY_PATH), str(labelled_models))
    # 如实记录的现状：端点段的标签在仓根没有文件，真实字节在 packaged 副本里（缺陷，见 docstring）
    assert labelled_endpoints.is_file() is False, labelled_endpoints
    assert model_catalog.PROVIDERS_PATH.as_posix().endswith(
        'design_lab/resources/repo/design-lab/config/provider-capabilities.json'), \
        model_catalog.PROVIDERS_PATH


def test_radar_catalog_follows_edited_registries_and_changes_nothing_else(monkeypatch, tmp_path):
    """登记行 05#L16|radar：目录是现读的，不是硬编码副本。

    证明：同一份文件被就地改写后，`catalog()` 的答复随之改变，而且只在我改的那一处变（逐指针
    diff 恰等于改动点，其余路径一字不变）：改台账 `observed_at` → 只有 `$.observed_at`；改某条
    `source.ref` → 只有 `$.models[0].source_ref`；改端点 `source` 字符串 → 只有
    `$.endpoints[2].source`；删掉一条台账 → 只有行数与该 placement 桶，别的行不动；改回原文件 →
    答复与基线整份相同（没有粘住的旧副本）。最关键一步：把 `machine_state` 从 WEIGHTS_COMPLETE
    升到 LOAD_VERIFIED（真探测档位），目录里只有 `$.models[0].machine_state` 变——`radar_state`、
    `default_enabled`、全部 counts 一字不变，`model_radar.resolve()` 仍按 UNQUALIFIED_RADAR_STATE
    拒绝该模型。探测过因此抬不起资格，数字也不是抄来的常量。

    没证明：这台机器真有 LOAD_VERIFIED 的权重（被改的是 tmp 里的合成台账）；HTTP 路由
    `/api/models` 的序列化（本节点只调 `catalog()`）；真实台账内容新鲜（那是上一节点的可追溯性）。
    """
    entry_a = _entry(machine_state='WEIGHTS_COMPLETE', local_path=_FIXTURE_LOCAL)
    entry_b = _entry(model_id='v09-radar-second-fixture',
                     source={'kind': 'vendor', 'ref': 'vendor:second/fixture', 'license_id': 'MIT'},
                     machine_state='METADATA_ONLY',
                     local_path='model-library:v09/second.safetensors')
    base_registry = _registry([entry_a, entry_b])
    base_providers = json.loads(model_catalog.PROVIDERS_PATH.read_text(encoding='utf-8'))

    registry_path = tmp_path / 'model-radar.json'
    providers_path = tmp_path / 'provider-capabilities.json'
    monkeypatch.setattr(model_radar, 'REGISTRY_PATH', registry_path)
    monkeypatch.setattr(model_catalog, 'PROVIDERS_PATH', providers_path)
    _write_json(registry_path, base_registry)
    _write_json(providers_path, base_providers)

    baseline = model_catalog.catalog()
    assert baseline['counts']['models'] == len(base_registry['entries']), baseline['counts']
    assert baseline['observed_at'] == base_registry['observed_at']

    def re_read(registry_document=None, providers_document=None):
        _write_json(registry_path,
                    base_registry if registry_document is None else registry_document)
        _write_json(providers_path,
                    base_providers if providers_document is None else providers_document)
        answered = model_catalog.catalog()
        return answered, _diff_paths(baseline, answered)

    stamp = '2026-02-02T02:22:22+00:00'
    answer, moved = re_read(_registry([entry_a, entry_b], observed_at=stamp))
    assert moved == ['$.observed_at'], moved
    assert answer['observed_at'] == stamp, answer['observed_at']

    relabelled = _entry(machine_state='WEIGHTS_COMPLETE', local_path=_FIXTURE_LOCAL,
                        source={'kind': 'huggingface', 'ref': 'huggingface/re-labelled-only-here',
                                'license_id': 'MIT'})
    answer, moved = re_read(_registry([relabelled, entry_b]))
    assert moved == ['$.models[0].source_ref'], moved
    assert answer['models'][0]['source_ref'] == 'huggingface/re-labelled-only-here'
    assert answer['models'][0]['placement'] == 'huggingface', answer['models'][0]

    which = 2
    old_source = base_providers['providers'][which]['source']
    edited_providers = json.loads(json.dumps(base_providers))
    edited_providers['providers'][which]['source'] = old_source + ' [v09 synthetic label]'
    answer, moved = re_read(providers_document=edited_providers)
    assert moved == [f'$.endpoints[{which}].source'], moved
    assert answer['endpoints'][which]['source'] == old_source + ' [v09 synthetic label]'
    assert answer['counts']['endpoints'] == len(base_providers['providers']), answer['counts']

    probed = _entry(machine_state='LOAD_VERIFIED', local_path=_FIXTURE_LOCAL)
    probed_registry = _registry([probed, entry_b])
    answer, moved = re_read(probed_registry)
    assert moved == ['$.models[0].machine_state'], moved
    assert answer['models'][0]['machine_state'] == 'LOAD_VERIFIED', answer['models'][0]
    assert answer['models'][0]['radar_state'] == 'WATCH', answer['models'][0]
    assert answer['models'][0]['default_enabled'] is False, answer['models'][0]
    assert answer['counts']['qualified_local'] == 0, answer['counts']
    assert answer['counts']['default_enabled_true'] == 0, answer['counts']
    with pytest.raises(ReadinessError, match='UNQUALIFIED_RADAR_STATE'):
        model_radar.resolve(probed_registry, _SYNTHETIC_MODEL_ID)

    answer, moved = re_read(_registry([entry_a]))
    # 少一行台账条目会带动这三个文档级计数与列表长度，其余格子一律不动
    assert moved == ['$.counts.models', '$.counts.placement.vendor',
                     '$.counts.weights_registered_none', '$.models[len]'], moved
    assert answer['counts']['models'] == 1, answer['counts']
    assert [row['model_id'] for row in answer['models']] == [_SYNTHETIC_MODEL_ID], answer['models']

    restored, moved = re_read()
    assert moved == [], moved
    assert restored == baseline, 'a stale copy of the ledger stayed in the answer'


def test_radar_qualification_cannot_be_minted_from_documentation_or_probe(monkeypatch, tmp_path):
    """登记行 05#L16|radar：资格既不来自"文档里写了"，也不来自"探测过"。

    证明：`catalog()` 对被台账规则拒绝的组合一律 fail closed，不返回半张目录——写了
    `default_enabled: true` 而 radar_state 不是 QUALIFIED_LOCAL → 拒（文档写了不算合格）；写了
    QUALIFIED_LOCAL + LOAD_VERIFIED 但没有登记的权重摘要 → 拒（探测档位不算合格）；补齐摘要但
    没有 `qualified_by` → 拒（没人署名的合格不存在）；写了 INFERENCE_VERIFIED 而没有
    `evidence_ref` → 拒（说跑过就得给凭据）；BLOCKED_BY_LICENSE 却带 FITS → 拒（读起来像就绪）；
    台账一条 entry 也没有 → 拒（空目录会被读成"没有候选"，那是另一种事实）。
    再给一份四样齐全的合法夹具：目录这才答出 QUALIFIED_LOCAL / weights_recorded 1 /
    default_enabled true，并且 `resolve()` 仍因 hardware_fit UNKNOWN 拒绝加载——探测、资格、
    适配各有各的键，谁也不能替谁开门。

    没证明：本机真能加载或推理那个模型（夹具全是合成字符串）；许可被裁定；真实台账里存在合格模型
    （它一条也没有，见前面节点的计数断言）。
    已修（本轮 I-a）：合法合格行的 `qualified_by`（是谁给的意见）与 `hash_source`（摘要从哪来）
    曾被 `_model()` 丢掉，选择面拿到的资格结论没有署名出处。两者现在原样透传，本节点末尾把
    「台账里的值 == 目录里的值」钉住；把它折叠进 `radar_state` 或不再透传都会让断言变红。
    """
    providers = json.loads(model_catalog.PROVIDERS_PATH.read_text(encoding='utf-8'))
    digest = 'a' * 64
    seen = []

    def refused(registry_document, match):
        seen.append(match)
        with pytest.raises(model_catalog.ModelCatalogError, match=match):
            _catalog_from(monkeypatch, tmp_path / f'case{len(seen)}', registry_document, providers)

    refused(_registry([_entry(default_enabled=True)]), 'default_enabled requires radar_state')
    refused(_registry([_entry(model_id='v09-radar-nohash-qualified',
                              radar_state='QUALIFIED_LOCAL', machine_state='LOAD_VERIFIED',
                              local_path=_FIXTURE_LOCAL)]), 'nonzero recorded weight hash')
    refused(_registry([_entry(model_id='v09-radar-noattributor',
                              radar_state='QUALIFIED_LOCAL', machine_state='LOAD_VERIFIED',
                              local_path=_FIXTURE_LOCAL, weights_sha256=[digest],
                              hash_source='synthetic')]), 'requires qualified_by')
    refused(_registry([_entry(model_id='v09-radar-inference',
                              machine_state='INFERENCE_VERIFIED', local_path=_FIXTURE_LOCAL,
                              evidence_ref=None)]),
            'INFERENCE_VERIFIED requires a non-empty evidence_ref')
    refused(_registry([_entry(model_id='v09-radar-blocked-fits',
                              radar_state='BLOCKED_BY_LICENSE', machine_state='WEIGHTS_COMPLETE',
                              local_path=_FIXTURE_LOCAL,
                              blocking_reason='licence not adjudicated in this test',
                              hardware_fit={'vram_gib_required': 2, 'verdict': 'FITS'})]),
            'may not carry a FITS hardware verdict')
    refused(_registry([]), 'refused to load')

    complete = _registry([_entry(model_id='v09-radar-qualified-ok',
                                 radar_state='QUALIFIED_LOCAL', machine_state='LOAD_VERIFIED',
                                 local_path=_FIXTURE_LOCAL, weights_sha256=[digest],
                                 hash_source='synthetic',
                                 qualified_by='owner (named human, synthetic fixture)',
                                 default_enabled=True)])
    answer = _catalog_from(monkeypatch, tmp_path / 'ok', complete, providers)
    row = answer['models'][0]
    assert row['radar_state'] == 'QUALIFIED_LOCAL', row
    assert row['machine_state'] == 'LOAD_VERIFIED', row
    assert row['weights_recorded'] == 1, row
    assert row['default_enabled'] is True, row
    assert row['source_ref'] == 'huggingface/' + _SYNTHETIC_MODEL_ID, row
    assert answer['counts']['qualified_local'] == 1, answer['counts']
    assert answer['counts']['weights_recorded'] == 1, answer['counts']
    assert answer['counts']['default_enabled_true'] == 1, answer['counts']
    # 署名与出处由台账带出，目录不替任何人编一个名字出来：格子等于台账说的话
    assert row['qualified_by'] == complete['entries'][0]['qualified_by'], row
    assert row['hash_source'] == complete['entries'][0]['hash_source'], row
    assert row['weights_state'] == 'RECORDED', row
    # 更强的事实：没有署名的资格结论连台账都进不来，目录因此没有可编名字的机会
    unsigned = json.loads(json.dumps(complete))
    unsigned['entries'][0]['qualified_by'] = None
    with pytest.raises(model_catalog.ModelCatalogError,
                       match='QUALIFIED_LOCAL requires qualified_by'):
        _catalog_from(monkeypatch, tmp_path / 'unsigned-sign', unsigned, providers)
    with pytest.raises(ReadinessError, match='hardware_fit is UNKNOWN'):
        model_radar.resolve(complete, 'v09-radar-qualified-ok')


def test_radar_weights_state_cannot_be_folded_back_onto_the_count(monkeypatch, tmp_path):
    """植入反证：把三态折叠回"看计数"，这一行的区分立刻不存在。

    证明的是断言能不能失败，而不是它现在是否为真：把 `_model()` 换成一个只按
    `weights_recorded` 决定状态的实现（0 就当作 REGISTERED_NONE，也就是把"没人说过"读成
    "登记了空列表"），同一份夹具下两种事实的状态格塌成同一个值、文档级 UNSTATED 计数归零；
    撤销补丁后复跑绿。顺带钉住状态格是投影自己算出来的：被读到的台账里没有这个名字的键。
    """
    providers = json.loads(model_catalog.PROVIDERS_PATH.read_text(encoding='utf-8'))
    omitted = _entry(model_id='v09-radar-fold-a')
    omitted.pop('weights_sha256')
    empty = _entry(model_id='v09-radar-fold-b', weights_sha256=[])
    registry = _registry([omitted, empty])

    honest = _catalog_from(monkeypatch, tmp_path / 'fold-honest', registry, providers)
    assert [row['weights_state'] for row in honest['models']] == ['UNSTATED', 'REGISTERED_NONE']

    original = model_catalog._model

    def fold_by_count(entry):
        row = original(entry)
        row['weights_state'] = 'RECORDED' if row['weights_recorded'] else 'REGISTERED_NONE'
        return row

    monkeypatch.setattr(model_catalog, '_model', fold_by_count)
    folded = _catalog_from(monkeypatch, tmp_path / 'fold-bad', registry, providers)
    assert len({row['weights_state'] for row in folded['models']}) == 1, folded['models']
    assert folded['counts']['weights_unstated'] == 0, folded['counts']
    monkeypatch.undo()
    restored = _catalog_from(monkeypatch, tmp_path / 'fold-restored', registry, providers)
    assert [row['weights_state'] for row in restored['models']] == \
        ['UNSTATED', 'REGISTERED_NONE'], restored['models']
    ledger = json.loads(Path(str(model_radar.REGISTRY_PATH)).read_text(encoding='utf-8-sig'))
    assert all('weights_state' not in row for row in ledger['entries']), \
        "状态格成了台账字段，投影就不再是自己算的"


def test_radar_catalog_document_satisfies_the_published_schema():
    """发布出去的 model-catalog-v1.schema.json 第一次真的被人拿来校验。

    普查发现的空档：这份 schema 有三份跟踪副本、`additionalProperties: false` 且把每一格都列进
    required，但仓库里没有任何代码或测试拿它校过目录答复——"公共合同"当时只是"有个文件"。
    本节点用发布的那份校验 `catalog()` 的真实答复（含本轮新加的 `weights_state`、两个出处格与
    文档级两个新计数），并要求三份副本逐字节相同：只改一份的话，合同就会以三种口径存在。
    """
    from jsonschema import Draft202012Validator

    document = model_catalog.catalog()
    schema_path = REPO_ROOT / "design-lab" / "schemas" / "model-catalog-v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    errors = sorted(Draft202012Validator(schema).iter_errors(document),
                    key=lambda error: list(error.absolute_path))
    assert errors == [], [(list(e.absolute_path), e.message) for e in errors][:6]

    copies = [schema_path,
              REPO_ROOT / "packages" / "contracts" / "schemas-design"
                       / "model-catalog-v1.schema.json",
              REPO_ROOT / "domains" / "design" / "design_lab" / "resources" / "repo"
                       / "design-lab" / "schemas" / "model-catalog-v1.schema.json"]
    assert all(path.is_file() for path in copies), [str(p) for p in copies if not p.is_file()]
    digests = {hashlib.sha256(path.read_bytes()).hexdigest() for path in copies}
    assert len(digests) == 1, digests
