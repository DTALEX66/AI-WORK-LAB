# DS-09 操作手册（只含已核验存在命令，2026-09-06）

> 支持 R3-09/10/16。所有命令都可在源码中找到定义；不包含不存在的入口。未来产品 API 在"待 GPT 提供"清单。

## 已核验命令

### design-lab doctor（便携工作区探测）
源码：`src/design_lab/runtime/doctor.py`（argparse 主体）；薄包装 `scripts/design_lab_doctor.py`。

```powershell
# 模块入口（含 --paths 等子项）
python -m design_lab.runtime.doctor --help
python -m design_lab.runtime.doctor --paths        # 项目路径解析与来源诊断
python -m design_lab.runtime.doctor --check        # 一致性检查
python -m design_lab.runtime.doctor --model-manifest --model-root <dir>
python -m design_lab.runtime.doctor --migration-preview
python -m design_lab.runtime.doctor --json         # JSON 输出
python -m design_lab.runtime.doctor --offline
python -m design_lab.runtime.doctor --version
# 薄包装等同调用（无自有参数）
python scripts/design_lab_doctor.py
```

### 其它已核验模块入口（均为库模块，非独立服务）
- `src/design_lab/runtime/state_store.py`：`init_db(db_path)` / `schema_version(conn)`（SQLite LocalStateStore v1）
- `src/design_lab/runtime/asset_store.py`：资产注册/版本/单写锁（T05）
- `src/design_lab/runtime/job_store.py`：Operation/Attempt 持久化（T05）
- `src/design_lab/runtime/profile_resolver.py`：R3-07 证据限定选择器（不授权执行）
- `src/design_lab/runtime/migration_preview.py`：只读迁移清单（不 copy/delete/mkdir/写 DB）
- `src/design_lab/runtime/paths.py`：项目路径解析（解析本身不建文件）
- `src/design_lab/runtime/attempt_contract.py`：verifier receipt 校验（≠宿主读回）
- `src/design_lab/analysis/model_cache.py`：模型缓存只读探测（fail-closed）
- `src/design_lab/generators/comfy_task.py`：生成任务协议/状态机（结构层，非服务器）

### Python 运行方式
```powershell
# 本项目 venv（Python 3.13.14 主环境；R3-09 的 3.12 产品资格 = GPT 处理）
.venv/Scripts/python.exe -B -m design_lab.runtime.doctor --paths
```

## 明确不在本清单（不伪造调用示例）
- `scripts/workflow/execution_preflight.py`：**当前树不存在**（已核实），不作可执行入口。
- 产品本地 API / OpenAPI / 前端 workbench：**尚无可验证入口**（R3-09/10 未实现前一律"待 GPT 提供"）。
- ComfyUI 服务器：`integrations/generators/comfyui/` 只有 manifest/evidence/policy，**不是真实服务器连通**。
- 宿主服务（AI/PS）：不存在可启动的 adapter server 声明。

## 局限
- 存在 adapter/manifest 文件 ≠ 已联通真实宿主；本条仅为接线资料，未实现新 API、未启动宿主服务。
