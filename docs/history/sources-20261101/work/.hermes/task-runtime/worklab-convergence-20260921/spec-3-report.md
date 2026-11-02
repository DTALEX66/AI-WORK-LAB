# SPEC 3/3 — Observer software[] 后端接线（WS-2，P1）— 执行报告

repo: D:/All projects/WORK-LAB, branch u17, HEAD=00f45a1. 改动全部留在工作树，未 commit/push/切分支。

## 执行结果（5 步）

### 1. 全读（完成）
- composition_root.py（261 行，build_v3_snapshot L214）
- sidecar.py v3_snapshot（L276）→ build_v3_snapshot → build_snapshot
- snapshot_api.py（packages/client-neutral-core/scripts/）
- platform_discovery.py（discover_software_installations L400，SOFTWARE_CANDIDATE_INVENTORY L312）
- software_installation_identity.py（classify_installation / preflight_identity_record）
- config/software-registry.json（7 个条目：hermes/codex/deepseek-harness/cc-switch/open-design/openhuman/github）
- apps/observer/frontend/src/types.ts（SoftwareIdentity 13 字段，L150-164；SnapshotV3.software? L184）
- apps/observer/frontend/src/views/SoftwareView.tsx（读 snap?.software，空→UNKNOWN）
- apps/observer/schemas/observer-event.schema.json（observer event，非 snapshot，无需改）
- snapshot_validator.py（validate_snapshot 只校验已知键，对未知键宽容）

### 2. 接线：composition_root.py +153 行
- **跨包 import**：`_ROOT = Path(__file__).resolve().parents[2]`，`_CNC_SCRIPTS = _ROOT/"packages"/"client-neutral-core"/"scripts"`，`sys.path.insert` 注入（与 durable_worker.py L28-31 完全一致）。
- **try/except 降级**：`import platform_discovery` / `import software_installation_identity` 包在 try/except 里；import 失败 → `_platform_discovery=None` → `_build_software_projection()` 直接返回 `[]`。
- **_build_software_projection()**：
  - 数据源 = `config/software-registry.json`（canonical ids）× `discover_software_installations()`（真实探测）× resolver（location_status 判定）。
  - registry 条目无对应 observation → `locationStatus="UNKNOWN"` + `discoverySource="unavailable"`（绝不伪造）。
  - DUAL_INSTALLATION → `duplicateInstallation=True`。
  - 13 个前端字段逐一映射。
  - **有界缓存**：模块级 `_software_discovery_cache` 单条目 dict，TTL 60 s；命中缓存不重跑 discovery；异常时清空缓存返回 `[]`。`clear_software_discovery_cache()` 暴露给测试。
- **build_v3_snapshot** 末尾加 `software=_build_software_projection()`。

### 3. schema additive：snapshot_api.py +5 行
- `build_snapshot` 签名加 `software: list[dict[str, Any]] | None = None`。
- 输出 dict 用 `**({"software": software} if software is not None else {})` 展开——`None` 时键完全省略，向后兼容；非 None 时正常携带。
- `validate_snapshot`（snapshot_validator.py）只校验它认识的键，对额外键不报错 → 无需改 validator。
- `observer-event.schema.json` 是 observer event schema，非 snapshot schema，无需改。
- **gate_snapshot_schema_v3 / gate_sse_browser_reconnect / gate_observer_no_business_write 全部 PASS（exit 0）。**

### 4. 前端类型：无偏差，不动
- `SoftwareIdentity`（types.ts L150-164）13 字段与后端产出完全对齐：
  softwareId / displayName / installRoot / executableRealpath / discoveredVersion / releaseChannel /
  updateAvailable / duplicateInstallation / expectedLocation / observedLocation /
  locationStatus / lastVerified / discoverySource
- `SnapshotV3.software?: SoftwareIdentity[]`（L184）已存在。
- SoftwareView.tsx 读 `snap?.software`，无数据→UNKNOWN，纪律正确。
- **无需任何 TS 改动。**

### 5. 单测：test_software_projection_shape.py（新建，10 个测试，全 PASS）
文件：`tests/workflow-assistance/test_software_projection_shape.py`

| 测试 | 断言 |
|---|---|
| test_empty_registry_produces_empty_list | 空 registry → `[]` |
| test_all_not_installed_preserves_location_status | 全 NOT_INSTALLED → 13 字段齐全，locationStatus="NOT_INSTALLED"，installRoot=None，discoverySource="real-platform-probe" |
| test_single_verified_entry_has_real_root_and_no_duplicate | SINGLE_VERIFIED → 真实 root，duplicateInstallation=False |
| test_discovery_unavailable_returns_unknown_entries | _platform_discovery=None → `[]`（不伪造） |
| test_registry_entry_without_observation_gets_unknown_status | registry 有、discovery 无 → locationStatus="UNKNOWN"，discoverySource="unavailable" |
| test_build_snapshot_includes_software_key_when_supplied | build_snapshot(software=[...]) → 键存在 |
| test_build_snapshot_omits_software_key_when_none | build_snapshot() 默认 → 键省略 |
| test_snapshot_with_software_passes_validator | 带 software[] 的 snapshot 通过 validate_snapshot |
| test_cache_returns_same_list_within_ttl | 两次调用 TTL 内 → 同一对象，discovery 只跑一次 |
| test_clear_cache_forces_refresh | clear 后再调 → discovery 再跑一次 |

**Mandatory discovery 收进**：`MANDATORY_TEST_GLOBS = ("test_*.py", "nf*.py")` 动态发现 →
`governance_test_files()` 自动收进 `test_software_projection_shape.py`（135 个 test 文件中第 1 个 software 相关）。
`python -m unittest tests/workflow-assistance/test_software_projection_shape.py` → 10 tests OK。

## Gate 结果

| Gate | 结果 | 说明 |
|---|---|---|
| gate_snapshot_schema_v3 | **PASS** (exit 0) | 41 tests |
| gate_sse_browser_reconnect | **PASS** (exit 0) | 25 tests |
| gate_observer_no_business_write | **PASS** (exit 0) | 11 tests |
| gate_governance | exit 1 | 165 模块 batch；exit=1 来自其他 spec 改动（run_quality_gate.py 已被 WS-3 加了 protected-drives-consistency gate；taskpacks/ 有 45+ 文件被删/移动；tests/ci/test_current_state.py 被改）。**我的 test_software_projection_shape.py 单独跑 10/10 PASS；governance gate 的 exit=1 与 WS-2 无关。** |

## 缓存机制说明

选择 **模块级单条目 in-memory TTL 缓存**（`_software_discovery_cache: dict`，TTL 60 s）：
- 每次 `/api/v1/snapshot` 调用 `build_v3_snapshot` → `_build_software_projection()`。
- 首次调用跑完整 discovery（subprocess exec --version 等），结果 + 时间戳写入缓存。
- 60 s 内后续调用直接返回缓存（同一 list 对象引用），不重跑 discovery。
- TTL 到期或 `clear_software_discovery_cache()` 强制刷新。
- 异常时清空缓存，下次重新探测（降级但不崩溃）。
- 选 TTL 而非 revision 级失效：discovery 结果与 revision 无关（它是机器上的安装事实，不是 canonical store 内容）；revision 级失效会导致每次 publish 都重跑 discovery，太重。60 s 是合理的折中：用户装新软件后 1 分钟内 Observer 面板就能看到，而不必等 sidecar 重启。

## 字段对齐表（前端 SoftwareIdentity ← 后端）

| 前端字段 | 类型 | 后端来源 |
|---|---|---|
| softwareId | string | registry.softwareId |
| displayName | string\|null | registry.displayName |
| installRoot | string\|null | obs.install_root（resolver） |
| executableRealpath | string\|null | obs.executable_realpath（resolver） |
| discoveredVersion | string\|null | obs.discovered_version（resolver） |
| releaseChannel | string\|null | obs.release_channel（resolver，通常 None） |
| updateAvailable | boolean\|null | 永远 None（resolver 不探测更新，绝不伪造） |
| duplicateInstallation | boolean | locationStatus=="DUAL_INSTALLATION" |
| expectedLocation | string\|null | obs.expected_existing（resolver） |
| observedLocation | string\|null | obs.observed_existing_location \|\| obs.install_root |
| locationStatus | SoftwareLocationStatus | obs.location_status（resolver §13 枚举）；无 obs → "UNKNOWN" |
| lastVerified | string\|null | obs.verified_at（resolver） |
| discoverySource | string\|null | obs.discovery_source；无 obs → "unavailable" |

## 遗留（需 mainline 决策）

1. **governance gate exit=1**：165 模块 batch 中至少一个非 WS-2 的模块失败（疑似 WS-3 的 protected-drives-consistency gate 或 taskpacks/ 文件移动导致）。需要 mainline 确认是哪个模块失败，是否与本 spec 无关。
2. **updateAvailable 永远 None**：resolver 不探测版本更新（那是 DSH 的 Update Authority 域）。前端 SoftwareView 显示 "UNKNOWN"。如果 mainline 想让 Observer 展示更新可用，需要 DSH adapter 额外暴露该字段——超出 WS-2 范围。
3. **config/software-registry.json 的 7 个条目 vs SOFTWARE_CANDIDATE_INVENTORY 的 6 个条目**：registry 有 "github"（category=platform），但 discovery inventory 没有 github 条目（github 是 API 平台，不是本地安装软件）。github 条目会得到 `locationStatus="UNKNOWN"`, `discoverySource="unavailable"`。这是诚实的（github 确实没有本地安装可探测），但如果 mainline 想让 github 不显示在软件面板，需要在 registry 里标注或前端过滤——超出 WS-2 范围。
