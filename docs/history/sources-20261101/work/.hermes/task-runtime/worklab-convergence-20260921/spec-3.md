# SPEC 3/3 — Observer software[] 后端接线（WS-2，P1）
repo: D:/All projects/WORK-LAB, branch u17 (HEAD 00f45a1). Do NOT: commit/push/branch switch; do NOT touch taskpacks/, .project/governance/, scripts/ci/, README.md, services/authority, services/policy（其他 SPEC 域）.

## mainline 已亲验的缺口
- 前端已备: apps/observer/frontend/src/views/SoftwareView.tsx 读 snap.software（SoftwareIdentity[]）, 无数据→UNKNOWN（正确纪律）; 类型在 frontend/src/types (SoftwareIdentity/SoftwareLocationStatus)。
- 后端缺: services/orchestration/composition_root.py build_v3_snapshot (L214) 输出字段 = revision/generated_at/source_watermark/store_projection/projects/executions/usage/ci_runs/transport/git_state/git_map/workspace/platform_map/agent_map —— 无 software; 且 composition_root 不引用 platform_discovery / software_installation_identity / config/software-registry.json。
- 生产 resolver 在 packages/client-neutral-core/scripts/platform_discovery.py: discover_software_installations()（只探 declared roots, CI 上多数 NOT_INSTALLED/UNKNOWN 属诚实值, 保留）+ resolve_software_installation()。
- 消费链: sidecar.py /api/v1/snapshot → v3_snapshot() → composition_root.build_v3_snapshot; SSE revision hub 推同一对象。

## 任务
1. 读全: composition_root.py 全文（含 build_snapshot 在哪个模块, 找它）+ sidecar.py v3_snapshot + apps/observer/schemas/observer-event.schema.json + apps/observer/frontend/src/types 中 SoftwareIdentity 定义（字段名逐一对齐: software/installRoot/executableRealpath/channel/duplicate/expectedLocation/observedLocation/locationStatus/lastVerified/discoverySource 等, 以前端类型为准）。
2. 接线: 在 build_v3_snapshot 增加 "software" 输出:
   - 数据源 = config/software-registry.json（canonical ids, 单一真值）× discover_software_installations()（真实探测结果）× resolve 判定, 逐软件生成前端 SoftwareIdentity 形状; 探测失败/未知 → 字段保持 "UNKNOWN" 或 null, 绝不伪造（truth discipline, 该仓现有 "绝不伪造" 注释风格）。
   - import 方式: platform_discovery 属 client-neutral-core scripts, 注意 composition_root 在 services/orchestration, 参考仓内既有跨包 import 惯例（git grep "client-neutral-core" services/ 看现成做法; 可能需要 sys.path 辅助, 对齐仓内脚本的 ROOT 计算）, 且探测必须 try/except 降级（探测全挂 → software=[] + discoverySource="unavailable", 不得让 snapshot 构建崩溃）。
   - 性能: 每次 /api/v1/snapshot 全跑 discovery 太重的话, 按仓内既有缓存模式（store/watermark/revision）做有界缓存（TTL 或 revision 级失效即可, 说明你选的机制）。
3. schema: 若 snapshot 有 machine schema（找 apps/observer/schemas/ 与 gate_snapshot_schema_v3 消费的 schema）, additive 加 software 字段（可选数组, 缺省合法）, 不许 break 现有 gate_snapshot_schema_v3 / gate_sse_browser_reconnect / gate_observer_no_business_write。
4. 前端类型: 若 SoftwareIdentity 字段与后端产出有偏差, 以最小改动对齐（可改 TS 类型, 不重构视图）; 无偏差则不动。
5. 负控 + 回归: 写一个单测（tests/workflow-assistance/ 下, test_* 命名, 只测你新增的 builder 函数: 空 registry/全 NOT_INSTALLED/一条 SINGLE_VERIFIED fixture 三种形态 → 断言输出形状 + UNKNOWN 纪律）, 并确认被 gate 的 mandatory discovery（test_*.py/nf*.py 动态发现）收进。

## 本地验证（terminal 走 wrapper）
- python services/orchestration/run_quality_gate.py verify （exit 0）
- 单独跑: gate_snapshot_schema_v3, gate_sse_browser_reconnect, gate_observer_no_business_write, gate_governance
- 若仓内已有 observer snapshot 冒烟（git grep -l "api/v1/snapshot" tests/ scripts/）, 跑一遍确认 software 键出现且 CI 环境全 UNKNOWN/NOT_INSTALLED 时形状合法
改动留工作树, 不 commit/push。报告: diff 摘要 + 字段对齐表 + 缓存机制说明 + gate 结果 + 遗留（如发现某 schema 需要 mainline 决策的点）
