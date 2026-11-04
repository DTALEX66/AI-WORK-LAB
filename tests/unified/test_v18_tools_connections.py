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
    assert body["counts"] == {"tasks": 0, "attempts": 0, "results": 0,
                              "attempts_with_pack_plan": 0, "pack_plan_check": "RUN"}, body

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
    assert after["counts"] == {"tasks": 1, "attempts": 1, "results": 0,
                               # this attempt was created without a pack binding, so there is no
                               # hop to resolve -- an empty problems list must not be read as
                               # "the pack hop was checked and passed"
                               "attempts_with_pack_plan": 0, "pack_plan_check": "RUN"}, after
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


# ------------------------------------------- GET /api/work/observer/projection -> usage
# Two register rows that said "没有专门断言" about their own acceptance wording:
#
# * `05#L7|usage` — 核心验收「实测与估计分开，未知不填0」. The producer was read, not
#   assumed. `usage_summary` is built in
#   `domains/work/workflow_core/canonical_store.py:1380-1409` (a GROUP BY over
#   `usage_samples`) and surfaced verbatim as the `usage` key of
#   `GET /api/work/observer/projection` by `backend/core/work_surfaces.py::observer_projection`
#   (route registered in `backend/core/work_surfaces.py::build_routes`). Row writes are
#   `canonical_store.py:677-753`: `input_tokens` / `output_tokens` / `total_tokens`
#   are measured counters, `cost_estimate` is the estimate and `cost_reconciled`
#   the reconciled (measured) cost; an absent counter is stored as NULL, and a row
#   nobody looked at carries `quality = "UNKNOWN"` — the only precision word the
#   in-repo usage collector writes for something it did measure is `EXACT_SOURCE`
#   (`domains/work/orchestration/collectors.py:365`).
# * `05#L31|unclassified` — 依据说明 said the 8/8 review is 文件自述 (NONE as
#   verification evidence). Recomputed below against `migration/mapping.csv`, which
#   is where a `source_key` is actually registered; the family vocabulary comes from
#   `migration/capability-family-register.csv`.

#: The key set `canonical_store.projection()` emits per provider/model group. Asserted
#: rather than assumed, because the acceptance wording is about WHICH key carries WHICH
#: kind of number — a shape this node can only check if the shape is pinned first.
#: The three `*_by_quality` / `*_coverage` maps are the answer to 「实测与估计分开」:
#: a token sum and a cost sum each travel with the precision word of the rows behind them.
USAGE_ITEM_KEYS = frozenset({"provider", "model", "samples", "samples_with_tokens",
                             "input_tokens", "output_tokens", "tokens", "observed_at",
                             "token_coverage",
                             "exact_source_samples", "unknown_quality_samples",
                             "measured_tokens", "unattributed_tokens",
                             "other_quality_tokens",
                             "samples_with_reconciled_cost", "samples_with_estimated_cost",
                             "cost_reconciled_total", "cost_estimate_total",
                             "quality_samples", "tokens_by_quality", "cost_coverage"})
#: "did not look" — the row's own declaration, not an inferred absence.
USAGE_UNSEEN_QUALITY = "UNKNOWN"
#: store column -> projected key, the three numbers the acceptance wording is about.
USAGE_NUMBER_COLUMNS = (("input_tokens", "input_tokens"), ("output_tokens", "output_tokens"),
                        ("total_tokens", "tokens"))


def _usage_groups_from_store(server) -> dict:
    """Group the store's own usage rows exactly the way the projection SQL groups them."""
    groups: dict[tuple, list] = {}
    for row in server.work.store.list_usage_samples():
        groups.setdefault((str(row["provider"]), str(row["model"])), []).append(row)
    return groups


def _usage_projection_items(server) -> dict:
    status, body = server.client.get("/api/work/observer/projection")
    assert status == 200, body
    assert isinstance(body["usage"], list), body
    index: dict[tuple, dict] = {}
    for item in body["usage"]:
        assert set(item) == USAGE_ITEM_KEYS, item
        pair = (str(item["provider"]), str(item["model"]))
        assert pair not in index, "投影把同一个 provider/model 投成了两行：" + repr(pair)
        index[pair] = item
    return index


def _known_sum(values: list) -> int | None:
    known = [value for value in values if isinstance(value, int) and not isinstance(value, bool)]
    return sum(known) if known else None


def _expect_red(action, message: str) -> str:
    """Run a checker that must fail, and hand back WHY it failed."""
    try:
        action()
    except AssertionError as failure:
        return str(failure)
    raise AssertionError(message)


def _assert_usage_unknown_is_never_a_zero(server, label: str) -> dict:
    """The live predicate for 「未知不填0」: recomputed from the store's own rows.

    Every projected number is re-added here from the raw `usage_samples` rows, and a
    group whose rows *all* declare `quality = "UNKNOWN"` must still answer null plus
    `token_coverage = "NONE"` — never 0, never an empty string. A measured 0 is still
    allowed to be 0, which is what keeps the two readings distinguishable.
    """
    groups = _usage_groups_from_store(server)
    index = _usage_projection_items(server)
    assert set(index) == set(groups), (label, sorted(index), sorted(groups))
    for pair, rows in groups.items():
        item = index[pair]
        assert item["samples"] == len(rows), (label, pair, item, rows)
        contributing = sum(1 for row in rows if row["total_tokens"] is not None)
        assert item["samples_with_tokens"] == contributing, (label, pair, item, rows)
        for column, key in USAGE_NUMBER_COLUMNS:
            assert item[key] == _known_sum([row[column] for row in rows]), (label, key, item, rows)
        for key in ("input_tokens", "output_tokens", "tokens"):
            assert item[key] is None or isinstance(item[key], int), (label, key, item)
            assert item[key] != "", (label, key, item)
        expected_coverage = ("NONE" if contributing == 0
                             else "FULL" if contributing == len(rows) else "PARTIAL")
        assert item["token_coverage"] == expected_coverage, (label, pair, item, rows)
        unseen = [row for row in rows if str(row["quality"]) == USAGE_UNSEEN_QUALITY]
        if len(unseen) == len(rows):
            for key in ("input_tokens", "output_tokens", "tokens"):
                assert item[key] is None, (
                    f"{label}：整组 {len(rows)} 行都声明 {USAGE_UNSEEN_QUALITY}（没看），"
                    f"{key} 却被投成了 {item[key]!r} —— 未知被填成了实测数字")
    return index


def test_usage_projection_never_renders_unknown_as_a_measured_zero(server):
    """register row `05#L7|usage` — 验收「未知不填0」这一半，现在是断言而不是推测。

    证明了什么：
    * 空库时 `GET /api/work/observer/projection` 的 `usage` 是 `[]` —— 一个用量都没有
      的时候，投影不替系统编出一行 0；
    * 三组合成分行（全 UNKNOWN / 实测为 0 / 只有 output 是实测、input 没看）逐组现算：
      投影里的 `input_tokens`、`output_tokens`、`tokens` 等于按 store 原始行重新加总的
      结果，`samples` 与 `samples_with_tokens` 等于现数行数，`token_coverage` 的词是从
      贡献行数推导的，不是抄来的；
    * 全部声明 `UNKNOWN` 的那一组，三个数字键都是 JSON null（不是 0、不是空串），
      `token_coverage` 是 `"NONE"`；而实测确实为 0 的那一组 `tokens == 0` 且
      `token_coverage == "FULL"` —— 「没看」和「看了、是 0」在同一个表面上是两种读数，
      这正是「未知不填0」要的东西；
    * 一行只有 output 实测、input 没看时，`input` 列保持 NULL，没有被补成 0；该行的
      派生 `total_tokens` 按已知加数求和（`canonical_store.py:686-692` 的
      `(inp or 0) + (out or 0)`），本节点只断言「未知列本身没有被填 0」，不背书这个
      派生和的语义。
    * 植入反证：把 UNKNOWN 行的三个 token 列按 0 写回（精度词仍是 UNKNOWN，只有数字
      变了），同一个谓词必须变红；还原后复跑必须变绿。

    没证明什么：不证明任何真实 provider 的真实用量；不证明这些数字来自真实采集
    （这里全部是合成 sample_id / provider）；不证明成本口径正确 —— 成本那一半见下一个
    节点；也不证明真实采集器不会写出「未知填 0」（采集器在这里一次都没被调用）。
    """
    store = server.work.store
    base = {"project_id": "v18-usage-project", "observed_at": "2026-01-01T00:00:00Z",
            "source_ref": "fixture:v18-usage"}
    unseen = {"sample_id": "v18-usage-unseen", "provider": "v18-usage-unseen",
              "model": "v18-model", "quality": USAGE_UNSEEN_QUALITY}
    measured_zero = {"sample_id": "v18-usage-measured-zero", "provider": "v18-usage-zero",
                     "model": "v18-model", "quality": "EXACT_SOURCE",
                     "input_tokens": 0, "output_tokens": 0}
    half_seen = {"sample_id": "v18-usage-half-seen", "provider": "v18-usage-half",
                 "model": "v18-model", "quality": "EXACT_SOURCE",
                 "input_tokens": None, "output_tokens": 7}

    # nothing recorded yet: the surface must not invent a zero-filled row
    assert _usage_projection_items(server) == {}

    for sample in (unseen, measured_zero, half_seen):
        store.record_usage_sample({**base, **sample})

    index = _assert_usage_unknown_is_never_a_zero(server, "基线")
    unseen_item = index[("v18-usage-unseen", "v18-model")]
    zero_item = index[("v18-usage-zero", "v18-model")]
    assert [unseen_item[key] for key in ("input_tokens", "output_tokens", "tokens")] == [None] * 3
    assert unseen_item["token_coverage"] == "NONE" and unseen_item["samples_with_tokens"] == 0
    assert zero_item["tokens"] == 0 and zero_item["token_coverage"] == "FULL"
    # 「没看」与「看了是 0」必须仍是两种可区分的读数
    assert unseen_item["tokens"] != zero_item["tokens"], (unseen_item, zero_item)
    assert unseen_item["token_coverage"] != zero_item["token_coverage"]
    half_row = next(row for row in store.list_usage_samples()
                    if row["sample_id"] == "v18-usage-half-seen")
    assert half_row["input_tokens"] is None and half_row["output_tokens"] == 7, half_row

    # 反证：同一个「没看」的行，只是把数字补成 0，精度词一个字没改
    store.record_usage_sample({**base, **unseen,
                               "input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
    try:
        red = _expect_red(
            lambda: _assert_usage_unknown_is_never_a_zero(server, "植入·未知被补成 0"),
            "植入反证失败：把 UNKNOWN 行的 token 全写成 0 之后，谓词仍然是绿的")
    finally:
        store.record_usage_sample({**base, **unseen})
    assert "没看" in red and "input_tokens" in red, red
    _assert_usage_unknown_is_never_a_zero(server, "还原")


def _assert_measured_and_estimated_costs_stay_on_separate_keys(server, label: str) -> dict:
    """The live predicate for 「实测与估计分开」: two keys, and no numeric collision.

    `cost_reconciled` is the reconciled (measured) money figure and `cost_estimate` is
    the estimate; the store keeps them in two columns and must keep them there. The
    check also requires that on the projected surface each figure shows up ONLY on its
    own cost key -- a money number on a token counter, a precision count or a coverage
    word would mean the two kinds of number were merged again.
    """
    rows = {str(row["sample_id"]): row for row in server.work.store.list_usage_samples()}
    exact, estimated = rows["v18-cost-exact"], rows["v18-cost-estimated"]
    assert exact["cost_reconciled"] == 1.5 and exact["cost_estimate"] is None, (label, exact)
    assert estimated["cost_estimate"] == 0.9 and estimated["cost_reconciled"] is None, (
        f"{label}：估计值 0.9 落到了实测键 cost_reconciled 上（现为 "
        f"{estimated['cost_reconciled']!r}）—— 实测与估计混成了同一个键")
    for row in (exact, estimated):
        for cost_key in ("cost_estimate", "cost_reconciled"):
            figure = row[cost_key]
            if figure is None:
                continue
            counters = (row["input_tokens"], row["output_tokens"], row["total_tokens"])
            assert figure not in counters, (label, cost_key, row)
    for item in _usage_projection_items(server).values():
        # 钱可以出现在投影里了 —— 但只许出现在自己那两把成本键上。token 计数器、
        # 精度计数与覆盖词里出现任何一个钱数，就说明两件事又被并成一个数。
        money_keys = frozenset({"cost_estimate_total", "cost_reconciled_total"})
        for key, value in item.items():
            if key in money_keys:
                continue
            assert value not in (0.9, 1.5), (label, key, value, item)
        for key, value in item.items():
            if value not in (0.9, 1.5):
                continue
            expected = "cost_estimate_total" if value == 0.9 else "cost_reconciled_total"
            assert key == expected, (label, key, value, item, expected)
    return rows


def test_usage_measured_and_estimated_costs_use_separate_keys(server):
    """register row `05#L7|usage` — 验收「实测与估计分开」那一半，分两段写。

    证明了什么（第一段，是真的证明）：
    * 写入层把「实测的钱」和「估计的钱」放在两把不同的键上：`cost_reconciled` 与
      `cost_estimate` 各自独立读写，一个缺席时另一把不会被顺带填上值，也没有任何 money
      数字等于同一行的 token 计数器（不会混进同一个数）；
    * 投影表面（`GET /api/work/observer/projection` 的 `usage`）里 0.9 与 1.5 都不出现
      —— 估计值没有从成本键渗到实测计数器上；
    * 反证：把估计值 0.9 并进实测键 `cost_reconciled` 之后，同一个谓词必须变红；还原后
      复跑必须变绿。

    第二段曾经钉的是缺陷：`canonical_store.projection()` 的 SELECT 里没有 `quality`、
    `cost_estimate`、`cost_reconciled` 三列（`domains/work/workflow_core/canonical_store.py`
    的 usage 查询），`backend/core/work_surfaces.py:98` 原样透出，所以投影只有
    `token_coverage` 一个词，而它描述的是「这组里有几行不是 NULL」，不是「这个数是量出来的
    还是估出来的」。现在那三列进了投影：每组带 `quality_samples`（EXACT_SOURCE / UNKNOWN /
    OTHER 三个计数）、`tokens_by_quality`（三档各自的 token 和）与 `cost_coverage`
    （实测钱与估计钱各自的覆盖词），混合组因此可复原，未识别的精度词进 `OTHER` 而不是消失。
    这一段现在钉的是这套拆分，并且按数据植入证明「 unrecognized 精度不会掉数」。

    节点性质不变：这一段本来就是「因修复而变红、届时改期望」的那一段——期望改了，断言没有
    放宽，反而多了（三档 token 之和必须等于 `tokens`，`OTHER` 必须由一条未识别精度的行实测出来）。

    没证明什么：不证明真实采集链路会写入 ESTIMATED/其它精度词（本仓 usage 采集器只写
    EXACT_SOURCE 与 UNKNOWN，见 collectors.py:243、:393；ESTIMATED 与 MEASURED_BY_HAND 都是
    这里的合成夹具）；不证明 v3 snapshot 的 `tokenSummary`（另一个表面，另有断言）。
    """
    store = server.work.store
    base = {"project_id": "v18-usage-project", "observed_at": "2026-01-01T00:00:00Z",
            "source_ref": "fixture:v18-usage"}
    exact = {"sample_id": "v18-cost-exact", "provider": "v18-cost-exact", "model": "v18-model",
             "quality": "EXACT_SOURCE", "input_tokens": 40, "output_tokens": 10,
             "cost_reconciled": 1.5, "cost_estimate": None}
    estimated = {"sample_id": "v18-cost-estimated", "provider": "v18-cost-estimated",
                 "model": "v18-model", "quality": "ESTIMATED", "input_tokens": 3,
                 "output_tokens": 2, "cost_estimate": 0.9}
    # 同一组的两个精度：一个量出来的 50，一个估出来的 7
    mixed = ({"sample_id": "v18-mixed-exact", "provider": "v18-usage-mixed", "model": "v18-model",
              "quality": "EXACT_SOURCE", "input_tokens": 20, "output_tokens": 30},
             {"sample_id": "v18-mixed-estimated", "provider": "v18-usage-mixed",
              "model": "v18-model", "quality": "ESTIMATED", "input_tokens": 5,
              "output_tokens": 2})
    estimated_only = {"sample_id": "v18-estimated-only", "provider": "v18-usage-estimated-only",
                      "model": "v18-model", "quality": "ESTIMATED", "input_tokens": 11,
                      "output_tokens": 4}

    for sample in (exact, estimated, estimated_only, *mixed):
        store.record_usage_sample({**base, **sample})

    # ---- 第一段：两把键，实测与估计互不冒充（真证明）
    _assert_measured_and_estimated_costs_stay_on_separate_keys(server, "基线")

    # 反证：把估计项并进实测键（0.9 同时写到 cost_reconciled 上）
    store.record_usage_sample({**base, **estimated, "cost_reconciled": 0.9})
    try:
        red = _expect_red(
            lambda: _assert_measured_and_estimated_costs_stay_on_separate_keys(
                server, "植入·估计并进实测键"),
            "植入反证失败：估计值 0.9 已经落在实测键 cost_reconciled 上，谓词仍然是绿的")
    finally:
        store.record_usage_sample({**base, **estimated, "cost_reconciled": None})
    assert "实测与估计混成了同一个键" in red, red
    _assert_measured_and_estimated_costs_stay_on_separate_keys(server, "还原")

    # ---- 第二段：投影把精度与成本拆开（这一段从"钉缺陷"改成"钉拆分"，断言只增不减）
    index = _usage_projection_items(server)
    assert {"quality_samples", "tokens_by_quality", "cost_coverage"} <= USAGE_ITEM_KEYS
    merged = index[("v18-usage-mixed", "v18-model")]
    assert (merged["input_tokens"], merged["output_tokens"], merged["tokens"]) == (25, 32, 57), merged
    # 50 是量出来的、7 是一行带着未识别精度词的行——现在分在两处，且三档之和就是那个和
    assert merged["quality_samples"] == {"EXACT_SOURCE": 1, "UNKNOWN": 0, "OTHER": 1}, merged
    assert merged["tokens_by_quality"] == {"EXACT_SOURCE": 50, "UNKNOWN": None, "OTHER": 7}, merged
    assert merged["measured_tokens"] == 50 and merged["other_quality_tokens"] == 7, merged
    assert merged["token_coverage"] == "FULL", merged
    estimated_group = index[("v18-usage-estimated-only", "v18-model")]
    assert estimated_group["tokens"] == 15 and estimated_group["token_coverage"] == "FULL"
    assert estimated_group["samples_with_tokens"] == 1 == estimated_group["samples"]
    # 全是未识别精度的组：一个实测数也拿不到，`token_coverage = FULL` 不再等于"量出来的"
    assert estimated_group["tokens_by_quality"] == {"EXACT_SOURCE": None, "UNKNOWN": None,
                                                   "OTHER": 15}, estimated_group
    assert estimated_group["quality_samples"]["EXACT_SOURCE"] == 0
    assert estimated_group["quality_samples"]["OTHER"] == 1, estimated_group

    # 钱的两侧：实测钱与估计钱各自带覆盖词，且不会因为另一侧有值就被顺带填上
    exact_group = index[("v18-cost-exact", "v18-model")]
    assert exact_group["cost_reconciled_total"] == 1.5, exact_group
    assert exact_group["cost_estimate_total"] is None, exact_group
    assert exact_group["cost_coverage"] == {"reconciled": "FULL", "estimated": "NONE"}, exact_group
    estimate_group = index[("v18-cost-estimated", "v18-model")]
    assert estimate_group["cost_estimate_total"] == 0.9, estimate_group
    assert estimate_group["cost_reconciled_total"] is None, estimate_group
    assert estimate_group["cost_coverage"] == {"reconciled": "NONE", "estimated": "FULL"}

    # 植入：一行带着投影不认识的精度词，也必须进 OTHER 而不是掉出表面
    store.record_usage_sample({**base, "sample_id": "v18-odd-quality",
                               "provider": "v18-usage-odd", "model": "v18-model",
                               "quality": "MEASURED_BY_HAND", "input_tokens": 4})
    odd = _usage_projection_items(server)[("v18-usage-odd", "v18-model")]
    assert odd["quality_samples"] == {"EXACT_SOURCE": 0, "UNKNOWN": 0, "OTHER": 1}, odd
    assert odd["tokens_by_quality"]["OTHER"] == 4, odd
    assert (sum(value for value in odd["tokens_by_quality"].values() if value is not None)
            == odd["tokens"]), odd
    # 每一组都要满足这个恒等式，否则拆档就是在偷数
    for pair, item in _usage_projection_items(server).items():
        parts = [value for value in item["tokens_by_quality"].values() if value is not None]
        assert (sum(parts) == item["tokens"]) if item["tokens"] is not None else not parts, (
            pair, item)
        assert sum(item["quality_samples"].values()) == item["samples"], (pair, item)


# ------------------------------------------------ migration/review/unclassified-review.json
#: `05#L31|unclassified` 的复核文件自述 8/8 已复核；`count_required` 在生成器里是字面量
#: （`scripts/build_migration_map.py:304-308`），`count_reviewed` 才是 `len(entries)`。
#: 真正的人口在 `migration/mapping.csv` 的 `初分能力族 == "unclassified"` 里，
#: `source_key` 也是在那里登记（`来源键`）；能力族词表来自
#: `migration/capability-family-register.csv` 的 `能力族ID` 列。全部现数，不抄 8。
UNCLASSIFIED_REVIEW_KEYS = frozenset({"reviewed_at", "count_required", "count_reviewed", "entries"})
UNCLASSIFIED_ENTRY_KEYS = frozenset({"source_key", "reviewed_family", "reason",
                                     "disposition", "target"})
UNCLASSIFIED_FAMILY = "unclassified"


def _read_register_csv(path):
    import csv

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _assert_unclassified_review_is_recomputable(review, mapping_rows, vocabulary, label: str) -> int:
    """Recompute the review from the registers instead of trusting its own words.

    Returns the live population size, which is the only place the "8" may come from.
    """
    assert set(review) == UNCLASSIFIED_REVIEW_KEYS, (label, sorted(review))
    entries = review["entries"]
    assert isinstance(entries, list), (label, type(entries))
    assert vocabulary, label + "：能力族词表是空的，任何 reviewed_family 都无从判定"

    by_key: dict[str, dict] = {}
    for row in mapping_rows:
        key = str(row["来源键"])
        assert key not in by_key, f"{label}：migration/mapping.csv 的来源键 {key} 重复，重算没有唯一锚点"
        by_key[key] = row
    population = {key for key, row in by_key.items() if row["初分能力族"] == UNCLASSIFIED_FAMILY}

    seen_keys: set[str] = set()
    seen_reasons: set[str] = set()
    for entry in entries:
        assert set(entry) == UNCLASSIFIED_ENTRY_KEYS, (label, sorted(entry))
        key = str(entry["source_key"])
        assert key in by_key, f"{label}：source_key {key!r} 在 migration/mapping.csv 里没有登记对象"
        assert key not in seen_keys, f"{label}：{key} 被复核了两遍"
        seen_keys.add(key)
        assert by_key[key]["初分能力族"] == UNCLASSIFIED_FAMILY, (
            f"{label}：{key} 的登记初分族是 {by_key[key]['初分能力族']!r}，不是未分类，"
            "这条复核不属于待复核人口")
        family = str(entry["reviewed_family"])
        assert family in vocabulary, (
            f"{label}：{key} 的 reviewed_family {family!r} 不在 capability-family-register.csv "
            "实际使用的能力族词表里")
        assert family != UNCLASSIFIED_FAMILY, f"{label}：{key} 复核后又回到了未分类"
        reason = entry["reason"]
        assert isinstance(reason, str) and reason.strip(), f"{label}：{key} 的 reason 是空的"
        assert reason not in seen_reasons, f"{label}：{key} 的 reason 与另一条逐字重复，不是逐条判断"
        seen_reasons.add(reason)
        assert entry["disposition"] == by_key[key]["处理方式"], (
            f"{label}：{key} 的处置 {entry['disposition']!r} 与映射登记 "
            f"{by_key[key]['处理方式']!r} 不一致")
        assert entry["target"] == by_key[key]["目标模块"], (
            f"{label}：{key} 的去向 {entry['target']!r} 与映射登记 "
            f"{by_key[key]['目标模块']!r} 不一致")

    unreviewed = sorted(population - seen_keys)
    assert not unreviewed, (
        f"{label}：{len(unreviewed)} 条未分类项没有第 {len(entries) + 1} 条复核，仍然悬着：{unreviewed}")
    assert not sorted(seen_keys - population), f"{label}：复核里有没有登记人口的 source_key"
    assert review["count_reviewed"] == len(entries), (
        f"{label}：count_reviewed 自述 {review['count_reviewed']}，entries 实际 {len(entries)} 条")
    assert review["count_required"] == len(population), (
        f"{label}：count_required 自述 {review['count_required']}，"
        f"mapping.csv 现数人口 {len(population)}")
    assert review["count_reviewed"] == review["count_required"], (
        f"{label}：已复核 {review['count_reviewed']} 条对不上待复核 {review['count_required']} 条")
    moment = datetime.fromisoformat(str(review["reviewed_at"]).replace("Z", "+00:00"))
    assert moment.tzinfo is not None, f"{label}：reviewed_at 没有时区：{review['reviewed_at']!r}"
    return len(population)


def test_unclassified_review_recomputes_from_the_mapping_population_not_from_its_own_words():
    """register row `05#L31|unclassified` — 把「已复核」从文件自述变成可复算的事实。

    证明了什么（全部现读现算，人口不是抄来的 8）：
    * 每一条 `source_key` 都在 `migration/mapping.csv` 的 `来源键` 里有唯一登记对象，
      并且该登记的 `初分能力族` 确实就是 `unclassified`（复核覆盖的是真人口，不是随手一行）；
    * 每一条 `reviewed_family` 都是 `migration/capability-family-register.csv`
      `能力族ID` 列里实际在用的词表值，且不等于 `unclassified`（复核不能把东西退回原地）；
    * 每一条 `reason` 去空白后非空，并且逐条互不相同（复制粘贴的判断不算复核）；
    * 每一条 `disposition` / `target` 与该 key 在 mapping.csv 里的 `处理方式` /
      `目标模块` 逐字一致 —— 依据说明点名的「重算条数与处置一致性」；
    * `count_reviewed == len(entries) == count_required == 现数人口`，而且集合相等两个
      方向都查：`{entry.source_key} == {初分能力族为 unclassified 的来源键}`，所以既没有
      第 9 条没被复核的未分类项，也没有一条不属于该人口的复核；
    * 顶层键集合固定，`reviewed_at` 带时区。
    * 植入四组反证（词表外族名 / 复制一条 reason / 处置漂移 / count_reviewed 自增）加
      一组人口反证（往 mapping 的副本里加第 9 条未分类项），每一次谓词都必须变红；
      最后一次用原始结构复跑必须变绿。

    没证明什么：不证明这些复核的**语义**是对的 —— 「这个模块该归 contracts 还是 project」
    是人的判断，本节点只能证明登记自洽、可复算、没有漏项；也不证明被复核对象在新仓真的
    存在（那是 05 表其它行的事）；反证只改内存副本，`migration/` 下的一个字节都没有落盘。
    """
    import copy
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    register_rows = _read_register_csv(root / "migration" / "capability-family-register.csv")
    mapping_rows = _read_register_csv(root / "migration" / "mapping.csv")
    assert register_rows and mapping_rows, "登记表读空了，重算没有意义"
    vocabulary = {str(row["能力族ID"]) for row in register_rows}
    assert UNCLASSIFIED_FAMILY in vocabulary, "capability-family-register.csv 里没有未分类族行"
    review_path = root / "migration" / "review" / "unclassified-review.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))

    population = _assert_unclassified_review_is_recomputable(
        review, mapping_rows, vocabulary, "基线")
    assert population >= 1, "现数人口为 0，等式两边都成立只是因为根本没有人口"
    assert review["count_reviewed"] == population

    # 反证 1-4：改复核文件本身（内存副本，不写盘）
    def mutate_family(document):
        document["entries"][0]["reviewed_family"] = "contract"

    def mutate_reason(document):
        document["entries"][1]["reason"] = document["entries"][0]["reason"]

    def mutate_disposition(document):
        entry = document["entries"][2]
        entry["disposition"] = "MERGE" if entry["disposition"] != "MERGE" else "RETAIN"

    def mutate_count(document):
        document["count_reviewed"] = document["count_reviewed"] + 1

    plants = (("把一条 reviewed_family 改成词表外的 contract", mutate_family, "词表"),
              ("把第一条 reason 逐字复制到第二条", mutate_reason, "逐字重复"),
              ("把一条处置改成与映射登记不一致", mutate_disposition, "不一致"),
              ("把 count_reviewed 自增一条，制造与 entries 数不符", mutate_count, "自述"))
    for description, mutate, expected_clause in plants:
        mutated = copy.deepcopy(review)
        mutate(mutated)
        red = _expect_red(
            lambda mutated=mutated, description=description: _assert_unclassified_review_is_recomputable(
                mutated, mapping_rows, vocabulary, "植入·" + description),
            "植入反证失败（" + description + "）：谓词仍然是绿的")
        assert expected_clause in red, (description, red)

    # 反证 5：人口里凭空多出第 9 条未分类项，复核一个字没改
    nine = copy.deepcopy(mapping_rows)
    ninth = dict(nine[0])
    ninth.update({"来源键": "synthetic:9th-unclassified#module", "初分能力族": UNCLASSIFIED_FAMILY,
                  "处理方式": "MERGE", "目标模块": "synthetic/never-landed"})
    nine.append(ninth)
    red = _expect_red(
        lambda: _assert_unclassified_review_is_recomputable(
            review, nine, vocabulary, "植入·多出第 9 条未复核的未分类项"),
        "植入反证失败：人口里加了一条没人复核的未分类项，谓词仍然是绿的")
    assert "没有第" in red and "synthetic:9th-unclassified#module" in red, red

    # 还原：原始结构复跑，仍然绿
    _assert_unclassified_review_is_recomputable(review, mapping_rows, vocabulary, "还原")
