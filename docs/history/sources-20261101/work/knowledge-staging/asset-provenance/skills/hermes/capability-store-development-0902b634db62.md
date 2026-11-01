---
name: capability-store-development
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/capability-store-development/SKILL.md
---

---
name: capability-store-development
description: "Use when working on ArcheAxis Capability Store (CAP-5xx)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [capability-store, plugin-manifest, capability-pack, builtin-plugins, archeaxis]
    related_skills: [test-driven-development, audited-project-delivery, project-data-boundary, regex-path-validation-pitfalls, python-testing]
---

# Capability Store / 插件清单 / Capability Pack 子系统（ArcheAxis-Knowledge-OS）

## 触发条件

涉及 app/capability/（store.py、router.py、builtin/）、contracts/plugin/、shared/plugin_manifest.py、scripts/capability_pack.py、scripts/capability_download.py 或 CAP-5xx 系列 ticket 时加载。本 skill 沉淀子系统契约事实（schema 枚举、store 生命周期、内置插件模式、pack 格式），避免每次重新逆向。

## 关键文件地图

- `contracts/plugin/plugin-manifest.schema.json` — manifest v1 的权威 JSON Schema（additionalProperties: false）
- `shared/plugin_manifest.py` — PluginManifest dataclass + validate()/load()/load_manifest_from_mapping()/is_compatible()
- `app/capability/store.py` — CapabilityStore v1（分区 + 原子生命周期）
- `app/capability/router.py` — /api/v1/capabilities 路由（store 按 ARCHEAXIS_CAPABILITY_ROOT env 每请求绑定）
- `app/capability/builtin/` — 内置转换插件（6 个适配器的注册模块 + discover()）
- `app/capability/conversion.py` — 转换调度层（AXW-CAP-503 step 2）：ConverterError / FileConverter / make_file_converter / ConversionDispatcher / 进程内激活注册表
- `scripts/capability_pack.py`、`scripts/capability_download.py` — pack 构建/校验 与 单工件下载治理

## Plugin manifest v1 契约（fail-closed）

- `manifest_version` 必须等于 `"1.0"`；`plugin_id` 正则 `^[a-z0-9][a-z0-9._-]{0,127}$`；`version` 必须 `x.y.z`
- `platform.os` 枚举 `windows/linux/macos/any` —— **不接受 "win32"**（ticket 里写 win32/x86_64 时用 `"windows"`，否则 validate 报 platform.os not allowed）；`platform.arch` 枚举 `x86_64/aarch64/arm64/any`
- `permissions` 枚举仅 6 个：files.read / files.write / network / process / model.load / ui.contribution；必须去重
- **`healthcheck` 字段是字符串**（探针规格，如 `"import:app.ingestion.docx_adapter"`），不是 callable；真正的探测函数由插件注册模块导出（见内置插件模式）
- `data_ownership` 形如 `{"declared": true, "note": "..."}`；`entry` 形如 `"module:function"`
- `validate()`：jsonschema 可用时走 schema，否则走等价手写校验器；两者都 fail-closed（未知字段/未知权限/坏平台一律 ValueError）。`load_manifest_from_mapping(dict)` 从已校验 dict 直接构造 PluginManifest
- `is_compatible(manifest, host_contract, platform)`：api_contract 范围相交 + 平台匹配；任何解析失败返回 False（绝不宽松默认）

## CapabilityStore 生命周期（store.py）

- 分区：`registry/ staging/ installed/ disabled/ quarantine/ packages/ plugins/`（plugins 为 AXW-CAP-503 内置插件登记分区）
- stage：校验 manifest → copytree 到 `staging/<sha256(manifest)[:16]>` + `.stage.json` sidecar；activate：重算 content hash（不符即拒绝，fail-closed）→ `os.replace` 原子移动到 `installed/<plugin_id>@<version>/` → 写 `.capability.json` + registry index.json
- `_compute_content_hash` 覆盖 pack 内**除 `.stage.json`/`.capability.json`/`.quarantine.json` 外**所有文件（按相对路径排序，path+bytes 混入哈希）——任何文件篡改都会被 activate 时的重算抓到
- disable/enable/quarantine 均为 os.replace 移动 + index 状态迁移；CapabilityRecord 是 frozen dataclass（`==` 逐字段比较，可用于幂等断言）
- `install_builtin(manifest, activator)`：幂等——已装则重算 hash 比对（篡改即 CapabilityStoreError），返回既有 record 且 **activator 不再调用**；首次把 manifest 写入 `installed/<id>@<version>/plugin-manifest.json`、登记 `plugins/<id>.json`（含 content_hash + manifest 副本）、调用 activator 一次
- 既有契约测试：`tests/test_axw_cap501_store.py`、`tests/test_axw_cap502_plugin_manifest.py`（改 store 必须保持全绿）

## 内置转换插件模式（app/capability/builtin/）

- 每适配器一个模块 `converters_<fmt>.py`：导出 schema 兼容的 `MANIFEST` dict + `healthcheck()` callable（`importlib.util.find_spec(ADAPTER_MODULE)` 探测，**绝不 import 重型模块**——find_spec 不执行模块顶层代码）
- `__init__.discover() -> list[PluginManifest]`：逐个 validate 后返回；任一非法即抛 ValueError（fail-closed，不静默跳过）。测试可用 monkeypatch 改某模块 MANIFEST 验证 fail-closed
- 6 个内置：docx/html/media/ocr/pptx/xlsx，`plugin_id = ax.builtin.converter.<fmt>`，`entry = app.ingestion.<adapter>:convert_<fmt>`；permissions 如实声明（media/ocr 含 `process`，因 ffmpeg/tesseract 子进程）

## 转换调度层（AXW-CAP-503 step 2：activator 真实接线）

- 每个 converters_<fmt>.py 导出 `get_activator() -> Callable[[], FileConverter]`：activate() 用 `conversion.make_file_converter()` 包装**真实适配器函数**（先读适配器源码拿签名，options 白名单 1:1 映射真实 kwargs：media=`work_dir`、ocr=`lang`），副作用 `register_active_converter()` 注册进进程内 registry
- 包装器 fail-closed：适配器 success=False / 抛异常 / 返回非 AdapterResult / 未知 options → `ConverterError`（绝不伪造成功）
- `ConversionDispatcher(store)`：`get_converter(id)` 仅当 record installed **且** 进程内已激活才返回 service，否则 None（不静默 fallback）；`list_active_converters()` = installed ∩ active
- **重启陷阱**：install_builtin 幂等路径不重调 activator（既有契约测试锁定，不许改 store）→ 重启后 registry 空、dispatch 全 None。解法：`builtin.activate_all_builtins(store)` 在 install_builtin 后查 `get_active_converter(id) is None` 则手动 `module.get_activator()()` 补注册
- 主链接入点（multi_format.convert_file / workspace 批量导入端点）暂不改：引擎链被大量既有测试锁定，交付调度层 + docstring 写明接入方式即可
- 测试在 `tests/test_axw_cap503_activator.py`（autouse fixture `reset_active_converters()` 隔离 registry；重适配器只验注册+调度+缺失文件 fail-closed）；完整模式、真实签名表、架构守卫豁免细节见 `references/activator-wiring.md`

## Capability Pack 格式（scripts/capability_pack.py）

- 输出 `<name>-<version>.pack.zip`（name/version 取第一个 manifest 的 plugin_id/version）；内部 layout：`pack.json` + `files/` 载荷
- `pack.json`：`pack_format=1`、name、version、created_at、`manifests[]`（已校验 dict）、`files[]`（每项 `path`/`size_bytes`/`sha256`，path 以 `files/` 前缀、禁绝对路径与 `..`）
- build 原子落盘：写 `.tmp` 后 `os.replace`；`verify` 重算每个文件 sha256，结构错/哈希不符/缺文件/孤儿文件/路径穿越一律 `PackBuildError` 拒绝（返回非零）
- capability_download.py 兼容：它是**单工件**治理 CLI（stage→verify→activate，下载 manifest 记整体 sha256），`.pack.zip` 作为一个文件直接 `stage file:// URL --license ...` + `verify` 即可消费，**接口零改动**；包内逐文件完整性由 pack.json/verify 与 store 的 stage→activate 哈希治理（此说明写进脚本 docstring）

## 验证铁律

- 测试命令（wrapper 单命令，禁串联/重定向）：
  `python "C:/Users/ALEX/AppData/Local/hermes/bin/hermes-project-data.py" --project . run -- env -u PYTHONPATH uv run --frozen --group ci --group ci-adapters pytest <files> -q --tb=short -p no:cacheprovider`
- ruff：先 `ruff check --fix`（I001 导入排序等自动修复），再 **`ruff format`**——format --check 同样是门禁，check 过了 format 不过照样红；改完重跑测试
- 测试 import scripts/ 模块直接 `from scripts.capability_pack import ...`（pytest pythonpath=["."]）；scripts/ 内 import shared 的姿势：模块顶部 `sys.path.insert(0, str(_PROJECT_ROOT))` + `# noqa: E402`
- 临时文件/CLI 冒烟产物放 `<project>/.hermes/task-runtime/tmp/`（gitignored）

## Pitfalls

- 平台写 `"windows"` 不写 `"win32"`（schema 枚举拒绝）
- 测试内 stage 本地文件用 `Path.as_uri()`；**命令行**冒烟被 terminal guard 拦绝对路径 URL 时改用相对 `file:` URL（见 regex-path-validation-pitfalls §4）
- install_builtin 幂等断言：二次调用返回与首次 `==` 相同的 record、activator 调用计数不变、已装 pack 篡改后重装抛 CapabilityStoreError
