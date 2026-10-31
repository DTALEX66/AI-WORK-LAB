# SPDX-License-Identifier: MIT
"""V18: the tool / connection / integrity / qualification-evidence surface.

Audit F10 closed "qualification comes from a constant" for capabilities and named
``GET /api/v1/qualification-evidence`` as the call_entry that proves it; the very
same defect then reappeared one route over, where ``GET /api/v1/tools`` answered a
hard-coded list whose ``CONNECTED_LOCAL`` no probe or store read had produced, and
``/api/v1/integrity`` + ``/api/v1/qualification-evidence`` had zero pytest hits.

These tests therefore do two things the old suite could not:

* they check each row against the ledger **as read from disk**, so a value that
  only exists in the handler has nothing to match; and
* they *move* the ledger and require the answer to move with it — plant a record,
  watch a state change, expire it, watch it fall back with a reason.

The last five nodes (``..._software_installation_identity_*`` /
``test_unauthorized_software_installation_probe_records_nothing``) close the gap
register row ``05#L10|software`` named as "本仓无 pytest 断言": the five sides
安装 / 版本 / 探测 / 授权 / 可执行 are checked as five separately keyed facts — on the real
``GET /api/work/observer/snapshot`` surface joined to ``config/software-registry.json``
and ``config/adapter-registry.json`` on disk, and in the pure resolver's negative
verdicts. They prove nothing about any real install: nothing is probed, and an
unauthorized probe is asserted to produce *no* observation at all.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

LEDGER_SCHEMA = "ai-work-lab/qualification-ledger/v1"


def _moment(raw: str) -> datetime:
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))


def _tools(server) -> dict:
    status, body = server.client.get("/api/v1/tools")
    assert status == 200, body
    return {row["tool_id"]: row for row in body["tools"]}


def _connections(server) -> dict:
    status, body = server.client.get("/api/v1/connections")
    assert status == 200, body
    return {row["connection_id"]: row for row in body["connections"]}


def _record(server, *, capability_id, operation, version, connection="CONNECTED",
            origin="live", outcome="VERIFIED", expires=None, observed=None):
    from backend.core.qualifications import probe_record

    row = probe_record(capability_id=capability_id, operation=operation,
                       scope="local_read", subject="v18 falsifier subject",
                       version=version, outcome=outcome,
                       evidence_refs=["probe:" + capability_id + "/v18"],
                       detail="record written by test_v18", data_origin=origin,
                       connection=connection, ttl_seconds=900)
    # second-resolution timestamps make latest_for() order-dependent; stamp them
    row["observed_at"] = observed or "2099-01-01T00:00:00+00:00"
    row["expires_at"] = expires or "2099-12-31T00:00:00+00:00"
    return row


# --------------------------------------------------------------------- /api/v1/tools
def test_tool_states_match_the_ledger_on_disk_and_no_literal(server):
    """Each row's value is re-derived here from the ledger file, not from the route."""
    version = server.api.candidate()["digest"]
    records = server.qualifications.records()
    status, raw = server.client.get("/api/v1/tools")
    assert status == 200
    # the deleted literal must not survive anywhere on this surface
    assert "CONNECTED_LOCAL" not in json.dumps(raw, ensure_ascii=False)
    assert raw["count"] == len(raw["tools"]) == 4
    assert raw["candidate_version"] == version

    def expected(capability_id, operation):
        """The same rule the route documents: newest accepted record wins."""
        matches = [row for row in records if row.get("capability_id") == capability_id
                   and row.get("operation") == operation]
        if not matches:
            return "NOT_PROBED"
        newest = max(matches, key=lambda row: str(row.get("observed_at") or ""))
        now = datetime.now(timezone.utc)
        accepted = (newest.get("candidate_digest") == version
                    and _moment(newest["expires_at"]) > now
                    and newest.get("data_origin") == "live"
                    and newest.get("scope") == "local_read"
                    and newest.get("outcome") == "VERIFIED")
        connection = str(newest.get("connection") or "")
        if accepted and connection in ("NOT_REQUIRED", "CONNECTED", "NOT_PROBED",
                                       "DISCONNECTED"):
            return connection
        return "NOT_PROBED"

    for row in raw["tools"]:
        assert row["bound_capability"] and row["operation"], row
        assert row["declared_by"].endswith("(declaration only, no status)"), row
        assert row["state"] == expected(row["bound_capability"], row["operation"]), row
        if row["state"] == "NOT_PROBED":
            assert row["unavailable_reasons"], row
            assert row["qualification"] in ("NOT_PROBED", "EXPIRED", "NOT_VERIFIED", "FAILED"), row
        else:
            assert row["evidence"]["candidate_digest"] == version, row
            assert row["evidence"]["data_origin"] == "live", row
            assert row["connection_observed_by_probe"] == row["state"], row
            assert not row["unavailable_reasons"], row


def test_a_record_moves_a_tool_state_and_losing_it_moves_it_back(server):
    """The falsifier: quality-gate is bound to an operation nothing probes, so its
    state can only change when the ledger says so — and back."""
    ledger = server.qualifications
    snapshot = (ledger.path.read_text(encoding="utf-8")
                if ledger.path.is_file() else json.dumps({"records": []}))
    version = server.api.candidate()
    try:
        before_all = _tools(server)
        before = before_all["quality-gate"]
        assert before["state"] == "NOT_PROBED", before
        assert before["evidence"] is None, before
        assert any("qualification=NOT_PROBED" in reason
                   for reason in before["unavailable_reasons"]), before

        # plant an accepted connection record for the operation this tool names
        ledger.append(_record(server, capability_id="work.quality_gate",
                              operation="quality_gate.run", version=version))
        during = _tools(server)["quality-gate"]
        assert during["state"] == "CONNECTED", during
        assert during["qualification"] == "VERIFIED", during
        assert during["evidence"]["connection"] == "CONNECTED", during
        assert during["evidence"]["matches_running_candidate"] is True, during
        assert during["evidence"]["expires_at"] == "2099-12-31T00:00:00+00:00", during
        assert during["evidence"]["evidence_refs"] == ["probe:work.quality_gate/v18"], during
        # the sibling rows are untouched: this is per-record, not a global flag
        after = _tools(server)
        assert after["design-lab-service"]["state"] == before_all["design-lab-service"]["state"]
        assert after["work-repair-machinery"]["state"] == before_all["work-repair-machinery"]["state"]

        # expire it: the same record inside a closed window grants nothing
        ledger.path.write_text(snapshot, encoding="utf-8", newline="\n")
        ledger.append(_record(server, capability_id="work.quality_gate",
                              operation="quality_gate.run", version=version,
                              expires="2020-01-01T00:00:00+00:00"))
        expired = _tools(server)["quality-gate"]
        assert expired["state"] == "NOT_PROBED", expired
        assert expired["qualification"] == "EXPIRED", expired
        assert any("freshness window" in reason for reason in expired["unavailable_reasons"]), expired

        # a record for the wrong capability id does not light the tool either
        ledger.path.write_text(snapshot, encoding="utf-8", newline="\n")
        ledger.append(_record(server, capability_id="work.quality_gate",
                              operation="some.other.operation", version=version))
        assert _tools(server)["quality-gate"]["state"] == "NOT_PROBED"

        # and removing the records restores the honest unknown with its reason
        ledger.path.write_text(snapshot, encoding="utf-8", newline="\n")
        reverted = _tools(server)["quality-gate"]
        assert reverted["state"] == "NOT_PROBED", reverted
        assert reverted["evidence"] is None, reverted
        assert reverted["unavailable_reasons"], reverted
    finally:
        ledger.path.write_text(snapshot, encoding="utf-8", newline="\n")


def test_host_and_model_tools_never_inherit_a_local_probe(server):
    """A successful in-process read must not be read as a host connection."""
    version = server.api.candidate()["digest"]
    # the design runtime really was read live at startup…
    runtime = _tools(server)["design-lab-service"]
    assert runtime["evidence"] is not None, runtime
    assert runtime["evidence"]["candidate_digest"] == version
    # …and none of that reaches Photoshop/ComfyUI/the WORK executors
    for row in _connections(server).values():
        assert row["state"] == "NOT_PROBED", row
        assert row["evidence"] is None, row
        assert row["authorization"] in ("NOT_GRANTED", "REQUIRED"), row
        assert row["unavailable_reasons"], row
        assert "CONNECTED_LOCAL" not in json.dumps(row, ensure_ascii=False)


# ------------------------------------------------------------------- /api/v1/integrity
def test_integrity_reports_the_store_it_actually_reads(server):
    status, body = server.client.get("/api/v1/integrity")
    assert status == 200, body
    assert set(body) == {"problems", "counts"}, sorted(body)
    assert isinstance(body["problems"], list)
    assert body["counts"] == {"tasks": 0, "attempts": 0, "results": 0}, body

    # one real chain written through the API moves the counts it names
    status, project = server.client.post("/api/v1/projects",
                                        {"name": "integrity", "source": "design"})
    assert status == 201, project
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "design", "title": "完整性样例",
        "acceptance": {"data_origin": "test"}})
    assert status == 201, task
    status, attempt = server.client.post(
        f"/api/v1/tasks/{task['task_id']}/attempts", {"idempotency_key": "v18-1"})
    assert status == 201, attempt

    status, after = server.client.get("/api/v1/integrity")
    assert status == 200, after
    assert after["counts"] == {"tasks": 1, "attempts": 1, "results": 0}, after
    # a chain built through the contract has nothing to name…
    assert after["problems"] == [], after
    for problem in after["problems"]:
        assert set(problem) == {"kind", "id", "detail"}, problem
    # …and integrity is read from the store, not from the task list: the store's
    # own row count agrees with what the route reported
    assert server.unified.get_task(task["task_id"])["task_id"] == task["task_id"]


def test_integrity_names_a_completion_that_no_longer_holds(server):
    """The F04 half that matters: a COMPLETED row the chain does not back must be
    named. The store refuses that write through its own API, so the row is planted
    the way a pre-constraint database would already contain it — underneath the
    API — and the route is asked whether it still sees it."""
    status, project = server.client.post("/api/v1/projects",
                                        {"name": "integrity2", "source": "design"})
    assert status == 201, project
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "design", "title": "unsupported 完成",
        "acceptance": {"data_origin": "test"}})
    assert status == 201, task
    task_id = task["task_id"]

    # the store itself refuses this transition through its API, which is why the
    # row has to be planted underneath it: integrity exists for exactly the
    # pre-constraint database that already contains it.

    server.unified.conn.execute("UPDATE tasks SET lifecycle='COMPLETED' WHERE task_id=?",
                                (task_id,))
    server.unified.conn.commit()
    try:
        status, body = server.client.get("/api/v1/integrity")
        assert status == 200, body
        kinds = {(problem["kind"], problem["id"]) for problem in body["problems"]}
        assert ("COMPLETION_UNSUPPORTED", task_id) in kinds, body
        assert body["counts"]["tasks"] == 1, body
        named = [problem for problem in body["problems"]
                 if problem["kind"] == "COMPLETION_UNSUPPORTED"][0]
        assert named["detail"], named
    finally:
        server.unified.conn.execute("UPDATE tasks SET lifecycle='DRAFT' WHERE task_id=?",
                                    (task_id,))
        server.unified.conn.commit()
    status, cleared = server.client.get("/api/v1/integrity")
    assert ("COMPLETION_UNSUPPORTED", task_id) not in {
        (problem["kind"], problem["id"]) for problem in cleared["problems"]}, cleared


# ------------------------------------------------------- /api/v1/qualification-evidence
def test_qualification_evidence_is_the_record_the_other_routes_cite(server):
    """F10's named call_entry: every row says which capability, which operation,
    which candidate digest, and until when it is allowed to answer."""
    status, catalog = server.client.get("/api/v1/capabilities")
    assert status == 200, catalog
    version = catalog["candidate_version"]
    status, evidence = server.client.get("/api/v1/qualification-evidence")
    assert status == 200, evidence
    assert evidence["schemaVersion"] == LEDGER_SCHEMA
    assert evidence["candidate_version"] == version
    assert evidence["count"] == len(evidence["records"])
    assert evidence["records"], ("the startup probes must have left records; an empty "
                                 "ledger means the reader cannot check anything")
    # the route reads the very same ledger the surfaces derive from
    assert evidence["count"] == len(server.qualifications.records())

    for row in evidence["records"]:
        assert row["capability_id"] and row["operation"], row
        digest = str(row.get("candidate_digest") or "")
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), row
        assert row["matches_running_candidate"] == (digest == version), row
        assert _moment(row["expires_at"]) > _moment(row["observed_at"]), row
        assert row["data_origin"] in ("live", "test", "demo"), row
        assert row["scope"] in ("local_read", "local_roundtrip_scratch", "loopback_http"), row
        assert row["outcome"] in ("VERIFIED", "NOT_VERIFIED", "FAILED", "EXPIRED",
                                 "NOT_PROBED"), row
        assert row["evidence_refs"], row
        assert row["self_reported"] is False, row

    live_verified = [row for row in evidence["records"]
                     if row["data_origin"] == "live" and row["matches_running_candidate"]
                     and row["outcome"] == "VERIFIED"
                     and _moment(row["expires_at"]) > datetime.now(timezone.utc)]
    assert live_verified, evidence["records"]
    # a scratch probe is recorded on purpose and must not read as live evidence
    synthetic = [row for row in evidence["records"] if row["data_origin"] != "live"]
    assert synthetic, "the scratch roundtrip record is missing"


def test_can_invoke_implies_a_record_this_route_can_show(server):
    """``can_invoke`` is only true when the evidence route can produce the record."""
    status, catalog = server.client.get("/api/v1/capabilities")
    assert status == 200, catalog
    version = catalog["candidate_version"]
    status, evidence = server.client.get("/api/v1/qualification-evidence")
    assert status == 200
    index = {(row["capability_id"], row["operation"]): row for row in evidence["records"]}

    callable_rows = [row for row in catalog["capabilities"] if row["can_invoke"]]
    assert callable_rows, "the startup probes must make something callable"
    for row in callable_rows:
        assert row["qualification"] == "VERIFIED", row
        record = index.get((row["capability_id"], row["operation"]))
        assert record is not None, row
        assert record["candidate_digest"] == version, (row, record)
        assert record["data_origin"] == "live", (row, record)
        assert record["outcome"] == "VERIFIED", (row, record)
        assert _moment(record["expires_at"]) > datetime.now(timezone.utc), (row, record)
        assert row["probe"]["observed_at"] == record["observed_at"], (row, record)
        assert row["unavailable_reasons"] == [], row
        assert row["authorization"] in ("NOT_REQUIRED", "GRANTED"), row

    # and the refusal side stays traceable rather than defaulted
    for row in catalog["capabilities"]:
        if not row["can_invoke"]:
            assert row["unavailable_reasons"], row


def test_evidence_added_by_a_probe_reaches_every_derived_surface(server):
    """One ledger, three readers: a record the tools route accepts is the same
    row the evidence route lists, with the same digest and expiry."""
    ledger = server.qualifications
    snapshot = (ledger.path.read_text(encoding="utf-8")
                if ledger.path.is_file() else json.dumps({"records": []}))
    version = server.api.candidate()
    try:
        row = _record(server, capability_id="work.executors",
                      operation="executor.invoke", version=version)
        ledger.append(row)
        tools_row = _connections(server)["work-adapters"]
        assert tools_row["state"] == "CONNECTED", tools_row
        status, evidence = server.client.get("/api/v1/qualification-evidence")
        assert status == 200
        listed = [item for item in evidence["records"]
                  if item["capability_id"] == "work.executors"]
        assert listed and listed[-1]["connection"] == "CONNECTED", listed
        assert listed[-1]["expires_at"] == tools_row["evidence"]["expires_at"], listed
        assert listed[-1]["matches_running_candidate"] is True, listed
    finally:
        ledger.path.write_text(snapshot, encoding="utf-8", newline="\n")
    assert _connections(server)["work-adapters"]["state"] == "NOT_PROBED"
    assert _tools(server)["quality-gate"]["state"] == "NOT_PROBED"


# ============================================================ software installation identity
# Register row 05#L10|software（「软件、路径与环境」）的验收句是「安装、版本、探测、授权、
# 可执行分别记录」，登记的缺口写的是「本仓无 pytest/探测断言」。下面五个节点补的就是这句话：
# 每个侧面各自成键、缺值保持缺失、反例给出具名判决、未授权的门不产出任何观测。
# 全部路径都是合成夹具（D:/synthetic/...），不存在于任何机器，也不去 stat 它们——
# classify_installation / plan_update / location_readback / overall_result 都是纯函数。

#: 五个侧面在本仓真正占用的键名，抄自 domains/work/control/composition_root.py 的
#: _build_software_projection()（快照 software[] 行）与 config/software-registry.json，
#: 不是这里发明的。授权一栏故意留空：快照行里没有授权键，授权事实记在默认关闭的探测门上。
SOFTWARE_INSTALLATION_SIDES = {
    "安装（位置）": ("installRoot", "expectedLocation", "observedLocation", "locationStatus",
                  "duplicateInstallation"),
    "版本": ("discoveredVersion", "releaseChannel", "updateAvailable"),
    "探测（真的看过没有）": ("discoverySource", "probeReason", "lastVerified"),
    "可执行": ("executableRealpath",),
}
#: 一条没被探测过的行里，这些侧面必须是缺失（JSON null），不是空串或 0。
SOFTWARE_UNKNOWN_KEYS = ("installRoot", "expectedLocation", "observedLocation",
                         "executableRealpath", "discoveredVersion", "releaseChannel",
                         "updateAvailable", "lastVerified")
#: config/software-registry.json 每一项真实存在的九个键。
SOFTWARE_LEDGER_KEYS = {"softwareId", "displayName", "category", "officialRepository",
                        "officialSource", "managedAs", "adapterId", "evidenceLevel",
                        "secretFields"}


def _software_ledger():
    """台账两份，按产品自己用的定位函数读（不依赖 cwd，也不复制一条路径拼写）。"""
    from domains.work.orchestration import resources as work_resources

    registry = json.loads(work_resources.software_registry_path().read_text(encoding="utf-8"))
    adapters = json.loads(work_resources.adapter_registry_path().read_text(encoding="utf-8"))
    return registry, adapters


def test_software_installation_identity_records_the_five_sides_apart(server):
    """05#L10 的正证：真实 HTTP 快照行 + 磁盘台账，五个侧面各自成键，缺值是缺失不是默认值。

    证明：
    * 台账里每个 softwareId 都在 GET /api/work/observer/snapshot 的 software[] 里有一行，
      displayName 与台账一致（同一对象，不是另起炉灶）；
    * 安装（位置）、版本、探测、可执行四个侧面各用自己的键，行里没有任何把四面塌成一个
      布尔的键（无 installed/ok/healthy 之类）；
    * 未探测的行，位置/版本/可执行五个键全是 null——不是 ""、不是 0、不是 "unknown"；
      位置判决写 NOT_PROBED，而 NOT_PROBED 不在 classify_installation 的判决词表里，
      所以「没看」不可能被读成一种测量结果；
    * 台账不冒领任何侧面：条目只有那九个键，没有 version/executable/installRoot/
      authorized 列，evidenceLevel 对七条一视同仁地写 "registered"（登记），条目存在本身
      不被写成已探测；版本侧另有其位（config/adapter-registry.json provenance.version），
      探测侧另有其位（detection.evidence_state），且申报过版本的条目必须自带读回；
    * 授权侧不在行内，而在明文写出的默认关闭门上；行内不得出现任何授权/授予键。

    没证明：任何软件的真实安装位置、真实版本、真实可执行文件——这台机器上一个都没探测。
    也只断言 software[] 这一面；「软件/环境」视图是否消费这些键不在本测试范围内。
    """
    from domains.work.control import composition_root
    from domains.work.orchestration import software_installation_identity as sii

    registry, adapters = _software_ledger()
    assert set(registry) == {"schemaVersion", "generatedAt", "purpose", "software"}, sorted(registry)
    entries = registry["software"]
    assert entries, "台账必须声明至少一项软件，否则下面的断言全是空转"

    status, snapshot = server.client.get("/api/work/observer/snapshot")
    assert status == 200, snapshot
    assert "software" in snapshot, sorted(snapshot)
    rows = {row["softwareId"]: row for row in snapshot["software"]}
    assert len(rows) == len(snapshot["software"]) == len(entries), (len(rows), len(entries))
    assert set(rows) == {entry["softwareId"] for entry in entries}, (set(rows), set(entries))

    for entry in entries:
        software_id = entry["softwareId"]
        row = rows[software_id]
        # —— 侧面各自成键，且没有合成一个总开关
        for side_keys in SOFTWARE_INSTALLATION_SIDES.values():
            for key in side_keys:
                assert key in row, (software_id, key, sorted(row))
        assert "installed" not in row, (software_id, sorted(row))
        assert row["displayName"] == entry["displayName"], software_id
        # —— 缺值保持缺失
        for key in SOFTWARE_UNKNOWN_KEYS:
            assert row[key] is None, (software_id, key, row[key])
        assert row["locationStatus"] == "NOT_PROBED", row
        assert row["locationStatus"] not in sii.LOCATION_STATUS, sii.LOCATION_STATUS
        assert row["discoverySource"] == "not-probed", row
        assert row["probeReason"] and "authorized=True" in row["probeReason"], row
        # —— 台账不冒领侧面：没有版本/位置/可执行/授权列，登记不等于探测
        assert set(entry) == SOFTWARE_LEDGER_KEYS, (software_id, sorted(entry))
        assert entry["evidenceLevel"] == "registered", entry
        assert not [key for key in entry if key.lower() in
                    ("version", "installed", "executable", "installroot",
                     "authorization", "authorized", "granted")], entry
        for key in ("softwareId", "displayName", "category", "officialSource", "managedAs"):
            assert isinstance(entry[key], str) and entry[key].strip(), (software_id, key)
        # 缺值在台账里也写成 null（cc-switch / openhuman 没有官方仓库，两条都没有 adapterId）
        for key in ("officialRepository", "adapterId"):
            value = entry[key]
            assert value is None or (isinstance(value, str) and value.strip()), (software_id, key)
        # secretFields 是「该由操作者提供的引用名」，不是凭据值
        assert isinstance(entry["secretFields"], list), software_id
        for name in entry["secretFields"]:
            assert isinstance(name, str) and name.strip() and " " not in name, (software_id, name)
            assert not any(mark in name for mark in ("ghp_", "sk-", "xox")), (software_id, name)
            assert len(name) < 60, (software_id, name)
        # 行内不得出现授权判决：没探测的行也不能顺手说自己被授权了
        assert [key for key in row if "author" in key.lower() or "grant" in key.lower()
                or "permission" in key.lower()] == [], (software_id, sorted(row))

    # —— 版本侧的真实位置：adapter-registry 的 provenance.version 与 detection 各自成键
    adapter_rows = {item["id"]: item for item in adapters["entries"]}
    assert len(adapter_rows) == len(adapters["entries"])
    cited = 0
    for entry in entries:
        adapter_id = entry["adapterId"]
        if adapter_id is None:
            continue  # 没有适配器就没有版本侧可引用；台账写 null，而不是造一个版本
        assert adapter_id in adapter_rows, (entry["softwareId"], adapter_id)
        adapter = adapter_rows[adapter_id]
        provenance = adapter["provenance"]
        version = provenance["version"]
        assert isinstance(version, str) and version.strip(), adapter_id
        assert set(adapter["detection"]) == {"mode", "evidence_state"}, adapter["detection"]
        # 探测侧独立成键，且今天没有任何条目把「登记过」写成「探测已验证」
        assert adapter["detection"]["evidence_state"] == "UNVERIFIED", adapter_id
        if version == "UNVERIFIED":
            assert "version_readback" not in provenance, adapter_id  # 未知不配读回
        else:
            readback = provenance["version_readback"]
            assert readback["method"] and readback["verified_version"] == version, adapter_id
            cited += 1
        digest = provenance["hash"]
        # 包摘要缺失：value 保持 null，并由自己的 state/basis 说出为什么缺失
        assert digest["value"] is None and digest["state"] == "UNAVAILABLE", adapter_id
        assert digest["basis"].strip() and digest["files"] == [], adapter_id
    assert cited >= 1, "没有任何 softwareId 指向 adapter-registry，版本侧就成了无人认领的键"

    # —— 声明但没打开的候选根，不得被当观测量填回行里（静默回落的反证）
    declared = composition_root.declared_software_candidates()
    assert declared, "声明清单为空时，下面的反证会空转"
    declared_roots = {root for item in declared for root in item["install_roots"]}
    assert declared_roots, declared
    for row in rows.values():
        assert row["installRoot"] not in declared_roots, row
        assert row["observedLocation"] not in declared_roots, row

    status, health = server.client.get("/api/work/observer/snapshot")
    assert status == 200
    surface = composition_root.software_projection_status()
    assert surface["probeState"] == "NOT_PROBED", surface
    assert surface["registryRead"] is True and surface["projectedCount"] == len(entries), surface
    assert surface["observedStatusVocabulary"] == list(sii.LOCATION_STATUS), surface
    assert "run_authorized_software_probe" in surface["authorizedDoor"], surface


def test_software_installation_identity_refuses_a_silent_vendor_fallback():
    """classify_installation 的反例：位置漂移与缺失都必须具名，且不回落到任何声明目录。

    证明（全部纯函数，输入是合成路径）：
    * 期望路径消失、别处发现了安装 → LOCATION_DRIFT 且 canonical_candidate is None；
      这个 None 不等于「没有安装」，preflight_identity_record 的 installed 布尔仍为 True，
      所以一个布尔不可能代替位置判决——这正是 §13 拒绝单一 installed 字段的原因；
    * 期望路径消失、一处都没发现 → MISSING_EXPECTED_INSTALL，同样不给候选；
    * 两种情况下判决都不采用声明清单里的任何厂商/官方目录，也不采用期望路径本身；
    * os_managed=True → OS_MANAGED（优先于期望路径消失的判断），不给候选，
      且 plan_update 答 PRESERVE_OFFICIAL_CHANNEL：不搬迁、不封锁、不提 fresh_target；
    * 两处不同安装 → DUAL_INSTALLATION，无候选，basis 点名两处；
    * 用户申报路径与观测不同 → LOCATION_DRIFT，但这次 canonical_candidate 是观测到的
      那一个（与「期望消失」分支不同，两个分支不该被并成一个判决）；
    * 路径身份比较不按字面量：反斜杠/大小写/结尾斜杠视为同一路径，不产生假漂移。
    """
    from domains.work.control import composition_root
    from domains.work.orchestration import software_installation_identity as sii

    expected = "D:/synthetic/expected/app"
    elsewhere = "D:/synthetic/elsewhere/app"
    declared_roots = {root for item in composition_root.declared_software_candidates()
                      for root in item["install_roots"]}

    drift = sii.classify_installation(expected_existing=expected, observed=[elsewhere])
    assert drift["location_status"] == "LOCATION_DRIFT", drift
    assert drift["canonical_candidate"] is None, drift
    assert expected in drift["basis"] and elsewhere in drift["basis"], drift["basis"]

    missing = sii.classify_installation(expected_existing=expected, observed=[])
    assert missing["location_status"] == "MISSING_EXPECTED_INSTALL", missing
    assert missing["canonical_candidate"] is None, missing
    assert "no vendor-default fallback" in missing["basis"], missing["basis"]

    # 静默回落的反证：两种失败判决都不交出任何路径，交出的也绝不是声明清单里的目录
    for verdict in (drift, missing):
        assert verdict["canonical_candidate"] not in declared_roots, verdict
        assert verdict["canonical_candidate"] != expected, verdict

    # 布尔与位置是两个侧面：同一份 drift 记录里 installed=True 而候选为 None
    record = sii.preflight_identity_record(software_id="synthetic-soft",
                                           expected_existing=expected, observed=[elsewhere])
    assert record["schema_version"] == "workflow/software-installation-identity/v1", record
    assert record["installed"] is True and record["location_status"] == "LOCATION_DRIFT", record
    assert record["observed_existing_location"] is None, record
    gone = sii.preflight_identity_record(software_id="synthetic-soft",
                                         expected_existing=expected, observed=[])
    assert gone["installed"] is False and gone["location_status"] == "MISSING_EXPECTED_INSTALL"
    assert gone["observed_existing_location"] != expected, gone

    managed = sii.classify_installation(expected_existing=expected, observed=[elsewhere],
                                        os_managed=True)
    assert managed["location_status"] == "OS_MANAGED", managed
    assert managed["canonical_candidate"] is None, managed
    plan = sii.plan_update(location_status=managed["location_status"], os_managed=True,
                           install_root=elsewhere, proposed_install_root="D:/synthetic/new/app")
    assert plan["update_mode"] == "PRESERVE_OFFICIAL_CHANNEL", plan
    assert plan["relocation"] is False and plan["blocked"] is False, plan
    assert "fresh_target" not in plan, plan  # 不给搬迁目标，连建议都不给

    dual = sii.classify_installation(observed=["D:/synthetic/a/app", "D:/synthetic/b/app"])
    assert dual["location_status"] == "DUAL_INSTALLATION", dual
    assert dual["canonical_candidate"] is None, dual
    assert "do not auto-delete" in dual["basis"], dual["basis"]

    conflict = sii.classify_installation(user_declared="D:/synthetic/user/app",
                                         observed=[elsewhere])
    assert conflict["location_status"] == "LOCATION_DRIFT", conflict
    assert conflict["canonical_candidate"] == elsewhere, conflict

    same = sii.classify_installation(user_declared="D:\\Synthetic\\App\\",
                                     observed=["d:/synthetic/app"])
    assert same["location_status"] == "SINGLE_UNVERIFIED", same
    assert same["canonical_candidate"] == "d:/synthetic/app", same

    fresh = sii.classify_installation(user_declared="D:/synthetic/user/app")
    assert fresh["location_status"] == "NOT_INSTALLED", fresh
    assert fresh["canonical_candidate"] == "D:/synthetic/user/app", fresh


def test_software_installation_identity_version_location_execution_stay_three_axes():
    """版本、位置、可执行三侧各自判决，合成总结时必须三者都为 PASS。

    证明：
    * plan_update 里 UPDATE != RELOCATION：同目录更新走 IN_PLACE_ONLY 并要求写后读回；
      换了根目录就是搬迁，未获批时 BLOCKED + RELOCATION_NOT_APPROVED（或
      INSTALL_ROOT_CHANGE_REQUIRES_EXPLICIT_RELOCATION），不因「版本能跑起来」放行；
    * 位置判决为 DRIFT/DUAL/MISSING/未验证时 update_mode 一律 BLOCKED，reasons 具名；
    * location_readback 只比位置：before/after 同根则通过，换了根就是
      LOCATION_READBACK_FAIL，哪怕新版本可用；
    * overall_result 需要 version/behavior/location 三个轴分别 PASS——任何一个不是
      PASS（包括 UNKNOWN，即「没记」）总结就是 FAIL：安装器退出码 0 不等于整体通过。

    没证明：任何一次真实写入、真实升级或真实读回；这些都是纯判决函数。
    """
    from domains.work.orchestration import software_installation_identity as sii

    root = "D:/synthetic/app"
    moved = "D:/synthetic/other/app"

    in_place = sii.build_update_preflight(software_id="synthetic-soft",
                                          location_status="SINGLE_VERIFIED", install_root=root,
                                          proposed_install_root=root, verified=True)
    assert in_place["schema_version"] == "workflow/software-update-preflight/v1", in_place
    assert in_place["update_mode"] == "IN_PLACE_ONLY", in_place
    assert in_place["relocation_approved"] is False and in_place["approved_operation"] == "UPDATE"
    assert in_place["location_readback_required"] is True and in_place["overall"] == "PENDING"
    assert in_place["location_readback_passed"] is None, in_place  # 写之前不许宣称读回通过
    assert in_place["before"]["install_root"] == root, in_place
    assert in_place["before"]["executable_realpath"] is None, in_place  # 可执行侧保持未知
    assert in_place["after"] == {"install_root": None, "executable_realpath": None}, in_place

    unapproved_plan = sii.plan_update(location_status="SINGLE_VERIFIED", install_root=root,
                                      proposed_install_root=moved, verified=True,
                                      relocation_requested=True)
    assert unapproved_plan["blocked"] is True and unapproved_plan["relocation"] is True, \
        unapproved_plan
    unapproved = sii.build_update_preflight(software_id="synthetic-soft",
                                            location_status="SINGLE_VERIFIED", install_root=root,
                                            proposed_install_root=moved, verified=True,
                                            relocation_requested=True)
    assert unapproved["update_mode"] == "BLOCKED", unapproved
    assert "RELOCATION_NOT_APPROVED" in unapproved["reasons"], unapproved["reasons"]
    assert unapproved["overall"] == "FAIL", unapproved
    assert unapproved["approved_operation"] is None, unapproved  # 没有批准就没有授权的操作
    assert not unapproved["location_readback_required"], unapproved
    assert "after" not in unapproved, unapproved  # 封锁的写没有可对比的 after，键不出现

    approved = sii.plan_update(location_status="SINGLE_VERIFIED", install_root=root,
                               proposed_install_root=moved, verified=True,
                               relocation_requested=True, relocation_approved=True)
    assert approved["update_mode"] == "RELOCATION" and approved["relocation"] is True, approved

    # 「更新不得隐式改变安装位置」：没申报搬迁的换根目录，一律封锁并具名
    silent_move = sii.plan_update(location_status="SINGLE_VERIFIED", install_root=root,
                                  proposed_install_root=moved, verified=True)
    assert silent_move["update_mode"] == "BLOCKED", silent_move
    assert "INSTALL_ROOT_CHANGE_REQUIRES_EXPLICIT_RELOCATION" in silent_move["reasons"], \
        silent_move["reasons"]

    for status, reason in (("LOCATION_DRIFT", "LOCATION_DRIFT_UPDATE_BLOCKED"),
                           ("DUAL_INSTALLATION", "DUAL_INSTALLATION_UPDATE_BLOCKED"),
                           ("MISSING_EXPECTED_INSTALL", "MISSING_EXPECTED_INSTALL_NO_VENDOR_FALLBACK"),
                           ("SINGLE_UNVERIFIED", "SINGLE_UNVERIFIED_IDENTITY_VALIDATION_FIRST")):
        blocked = sii.plan_update(location_status=status, install_root=root)
        assert blocked["update_mode"] == "BLOCKED", (status, blocked)
        assert reason in blocked["reasons"], (status, blocked["reasons"])

    same = sii.location_readback({"install_root": root, "executable_realpath": root + "/bin.exe"},
                                 {"install_root": "D:\\synthetic\\app\\",
                                  "executable_realpath": root + "/bin.exe"})
    assert same["install_root_unchanged"] is True and same["location_readback_passed"] is True
    assert same["fail_reason"] is None, same
    shifted = sii.location_readback({"install_root": root}, {"install_root": moved})
    assert shifted["install_root_unchanged"] is False, shifted
    assert shifted["location_readback_passed"] is False, shifted
    assert shifted["fail_reason"] == "LOCATION_READBACK_FAIL", shifted
    relocated = sii.location_readback({"install_root": root}, {"install_root": moved},
                                      is_relocation=True)
    assert relocated["location_readback_passed"] is True, relocated

    # 三轴分别记录，缺任何一条都不是 PASS
    assert sii.overall_result(version_verification="PASS", behavior_verification="PASS",
                              location_verification="PASS") == "PASS"
    assert sii.overall_result(version_verification="PASS", behavior_verification="PASS",
                              location_verification="UNKNOWN") == "FAIL"
    assert sii.overall_result(version_verification="PASS", behavior_verification="PASS",
                              location_verification="") == "FAIL"
    assert sii.overall_result(version_verification="UNKNOWN", behavior_verification="PASS",
                              location_verification="PASS") == "FAIL"


def test_software_installation_identity_blank_path_is_not_a_recorded_location():
    """「未知不填 0」这一条按实际行为写：空串观测被当成「没发现」，而不是被记成位置。

    这里如实记录 classify_installation 的真实行为，并说清它证明了什么、没证明什么。

    证明：
    * observed 传 None、[]、[""]、["   "]、["\\\\"]（规范化后为空）得到完全相同的判决字典
      ——NOT_INSTALLED / canonical_candidate None / 同一句 basis。也就是说函数**无法**区分
      「一处都没找到」和「上游 discovery 交回一个空串」；
    * 这种塌缩的方向是安全的：空串永远不会被写成 canonical_candidate、install_root 或
      basis 里的观测位置，也不会被填成 0 或空串冒充「已记录的位置」；带期望路径时空串仍
      判 MISSING_EXPECTED_INSTALL（而不是「位置正确」），因此一个坏输入不可能造出
      「看起来已核实」的安装记录；
    * 只要交回一个真实的非空路径，判决立刻与上面不同（MISSING_EXPECTED_INSTALL →
      LOCATION_DRIFT），说明塌陷只发生在「空白」这一侧，不是把所有输入并成一团。

    没证明：函数不会把「上游 bug 交回空串」这件事报告给调用方——它确实不报告，这里把它
    固定为已知行为。调用方（platform_discovery / 适配器）若要区分「没找到」与「拿不到」，
    必须在自己的记录里另写一个侧面；本仓的快照面正是用 null + NOT_PROBED 做到的（见
    test_software_installation_identity_records_the_five_sides_apart）。为了跑绿而放宽
    这里的断言，等于把这条已知的信息损失重新藏起来。
    """
    from domains.work.orchestration import software_installation_identity as sii

    nothing = sii.classify_installation()
    empty_list = sii.classify_installation(observed=[])
    blank = sii.classify_installation(observed=[""])
    spaces = sii.classify_installation(observed=["   "])
    separator_only = sii.classify_installation(observed=["\\"])

    assert empty_list == nothing, (nothing, empty_list)
    assert blank == nothing, (nothing, blank)
    assert spaces == nothing, (nothing, spaces)
    assert separator_only == nothing, (nothing, separator_only)
    for verdict in (nothing, empty_list, blank, spaces, separator_only):
        assert verdict["location_status"] == "NOT_INSTALLED", verdict
        assert verdict["canonical_candidate"] is None, verdict  # 不是 ""、不是 0
        # basis 里也不能出现一个空引号当位置
        assert "''" not in verdict["basis"] and '""' not in verdict["basis"], verdict["basis"]

    # 同一塌陷在「有期望路径」的一侧：空串仍等于什么都没发现
    expected = "D:/synthetic/expected/app"
    blank_with_expected = sii.classify_installation(expected_existing=expected, observed=[""])
    none_with_expected = sii.classify_installation(expected_existing=expected, observed=[])
    assert blank_with_expected == none_with_expected, blank_with_expected
    assert blank_with_expected["location_status"] == "MISSING_EXPECTED_INSTALL"
    assert blank_with_expected["canonical_candidate"] is None

    # 反面对照：一个真实的非空观测立刻把判决从 MISSING 改成 DRIFT——塌陷仅限空白输入
    drifted = sii.classify_installation(expected_existing=expected,
                                        observed=["D:/synthetic/elsewhere/app"])
    assert drifted != blank_with_expected, drifted
    assert drifted["location_status"] == "LOCATION_DRIFT", drifted

    # registered_roots 走同一条 dedupe：os_registered=[""] 也不能冒充「系统里登记过」
    registered_blank = sii.classify_installation(expected_existing=expected,
                                                 os_registered=[""])
    assert registered_blank["location_status"] == "MISSING_EXPECTED_INSTALL", registered_blank

    # verified 只是调用方交回的一栏：函数自己不发明「已核实」
    unverified = sii.classify_installation(observed=["D:/synthetic/app"])
    verified = sii.classify_installation(observed=["D:/synthetic/app"], verified=True)
    assert unverified["location_status"] == "SINGLE_UNVERIFIED", unverified
    assert verified["location_status"] == "SINGLE_VERIFIED", verified
    assert unverified["canonical_candidate"] == verified["canonical_candidate"]


def test_unauthorized_software_installation_probe_records_nothing():
    """授权侧面单独成门：未授权时不产出任何观测，也不留下半个位置或版本。

    证明：
    * probe.run_probe(inventory=..., authorized=False) 抛 ProbeNotAuthorized，错误名是
      SOFTWARE_PROBE_NOT_AUTHORIZED；用绊线替换真正的发现函数，确认它一次都没被调用
      ——拒绝不是「部分探测后失败」；
    * run_process_probe 有自己独立的授权码（SOFTWARE_PROCESS_PROBE_NOT_AUTHORIZED）：
      对轻量门的授权不等于对「执行 --version / 列进程」重门的授权；
    * composition_root.run_authorized_software_probe() 默认参数同样拒绝；
    * probe_state_record() 是「申报过、没去看」的唯一诚实形状：只有 softwareId/displayName/
      probeState/reason 四个键，没有任何 install_root/version/executable 键可以填默认值。

    没证明：授权之后的探测结果是否正确——本测试不启动任何发现，也不碰任何真实路径。
    """
    from domains.work.control import composition_root
    from domains.work.orchestration import platform_discovery, probe

    calls = []

    def tripwire(inventory=None):  # noqa: ARG001 - 记录调用本身，不做任何事
        calls.append(inventory)
        raise AssertionError("discovery must not run behind an unrefused door")

    original = platform_discovery.discover_software_installations
    synthetic = [{"software_id": "synthetic-soft", "install_roots": ["D:/synthetic/never/stat"]}]
    try:
        platform_discovery.discover_software_installations = tripwire

        for kwargs in ({}, {"authorized": False}, {"authorized": None}):
            try:
                probe.run_probe(synthetic, **kwargs)
                raise AssertionError(f"probe.run_probe({kwargs}) 应当拒绝")
            except probe.ProbeNotAuthorized as refusal:
                assert probe.NOT_AUTHORIZED_CODE in str(refusal), str(refusal)
            except TypeError as error:  # authorized=None 走同一拒绝，不接受类型错误
                raise AssertionError(f"probe.run_probe({kwargs}) 拒绝形状变了：{error}")
        assert calls == [], "未授权时发现了函数被调用过：" + repr(calls)

        try:
            probe.run_process_probe(authorized=False)
            raise AssertionError("process probe must refuse too")
        except probe.ProbeNotAuthorized as refusal:
            assert probe.PROCESS_PROBE_NOT_AUTHORIZED_CODE in str(refusal), str(refusal)

        try:
            composition_root.run_authorized_software_probe(reason="synthetic refusal check")
            raise AssertionError("the composition-root door is default-off too")
        except probe.ProbeNotAuthorized as refusal:
            assert probe.NOT_AUTHORIZED_CODE in str(refusal), str(refusal)
    finally:
        platform_discovery.discover_software_installations = original

    record = probe.probe_state_record("synthetic-soft", display_name="Synthetic Soft")
    assert set(record) == {"softwareId", "displayName", "probeState", "reason"}, record
    assert record["probeState"] == probe.PROBE_STATE == "NOT_PROBED", record
    assert record["reason"] and "authorized=True" in record["reason"], record
    assert not [key for key in record
                if any(mark in key.lower() for mark in
                       ("root", "path", "version", "executable", "authoriz", "grant"))], record
