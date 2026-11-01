# DLR-040: 能力库减法重构计划

## 当前状态

- `capability-index.json`：2424 项（458KB），包含所有文件（README、LICENSE、requirements、SKILL.md 等）
- 真正的 adapter manifest：5 个（`adapter.manifest.json`）
- SOURCE_REGISTRY.json：6 个 active 条目
- QUARANTINE_REGISTRY.json：162 个隔离条目

## 问题

1. **能力索引把文件当能力**：README、LICENSE、requirements、安装器/规则等被计算为 capability
2. **没有显式 capability manifest**：当前索引基于文件存在，不是显式声明
3. **第三方指令进入活跃面**：vendored AGENTS/CLAUDE/cursorrules 被索引

## 重构方案

### Phase 1: 创建 capability manifest schema（当前）

创建 `design-lab/schemas/capability-manifest.schema.json`，定义显式 capability 的必需字段：
- `capabilityId`：唯一标识
- `owner`：负责模块
- `consumer`：使用方
- `schema`：数据 schema
- `tests`：测试文件
- `source`：源码路径
- `license`：许可证
- `hash`：内容 hash
- `evidenceLevel`：E0-E5

### Phase 2: 迁移现有 adapter manifest（下一步）

将 5 个 `adapter.manifest.json` 迁移到新的 capability manifest 格式：
- `adapters/hosts/open-design/`
- `adapters/creative-tools/comfyui/`
- `adapters/creative-tools/adobe/`
- `adapters/creative-tools/minimax-h3/`
- `adapters/mcp/`

### Phase 3: 重构 capability-index.json（后续）

- 只接受显式 `capability.manifest.*`
- 移除所有非 capability 文件（README、LICENSE、requirements 等）
- 从 2424 项收敛到真实 capability 数量

### Phase 4: 更新 generate_project_status.py（后续）

- 更新 capability 计数逻辑
- 只计算显式 capability manifest

## 执行顺序

1. ✅ DLR-000/010/020/030/050（已完成）
2. 🔄 DLR-040 Phase 1（当前）
3. ⏳ DLR-040 Phase 2-4（后续）
4. ⏳ DLR-060（Design IR v2）
5. ⏳ DLR-070（Open Design 主宿主采用）
6. ⏳ DLR-100（五黄金案例）

## 验收标准

- capability-index.json 只包含显式 capability manifest
- 每个 capability 有 owner、consumer、schema、tests、source、license、hash、evidence level
- README/LICENSE/requirements 不计能力
- quarantine 内容无法自动激活

## 创建时间

- 创建者：DLR-040 任务
- 创建时间：2026-08-26
- 基线 SHA：`244c18f`
