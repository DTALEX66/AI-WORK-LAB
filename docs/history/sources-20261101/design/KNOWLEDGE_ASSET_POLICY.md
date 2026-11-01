# KNOWLEDGE_ASSET_POLICY — 外置资料库与来源资产治理

版本：1.0（2026-08-14）
适用：`DTALEX66/DESIGN-LAB` 仓库 + 外置资料库（`D:\All projects\Design assets` 或等价主机位置）
状态：强制治理合同；违反即失败关闭，不得进入能力层或发布证据。

## 1. 数据所有权与位置边界

- **原件永不入 Git**：原图、模型、字体、PDF、视频、音频、完整第三方前端等二进制/大体积物料，一律留在外置资料库。
- 外置资料库**仅登记**：仓库只保存登记记录（SourceRecord），不复制、不索引、不镜像原件。
- 仓库 Git 只接受：`SourceRecord` → 提取结果 → `MethodCard` / `ReferenceSet` / `Rubric` / `Benchmark`。
- 禁止：批量复制、自动索引外置库根目录、把原图/模型/字体直接入 Git、以符号链接或 junction 绕过边界。

## 2. SourceRecord 准入合同（每项必填）

每个来源记录必须满足 `design-lab/schemas/source-record.schema.json` 的 required 字段，并额外强制：

| 字段 | 要求 |
|---|---|
| `sourceId` | 稳定唯一 ID |
| `origin` | 原始 URL/出处（不匿名化） |
| `author` | 权利人/作者 |
| `license` | SPDX 标识或明确条款 |
| `licenseStatus` | `reviewed` / `unknown` / `reference-only`；`unknown` 不得进入生成 |
| `allowedUsage` | 允许用途（参考/派生/适配/商用） |
| `version` | 版本或 commit pin（Git 来源必须记录 commit SHA） |
| `contentHash` | **SHA-256**（原件哈希，入库前计算并回读校验） |
| `redistributable` | 是否可再分发 |
| `modelInputAllowed` | 是否允许进入模型输入 |
| `commercialUse` | 是否允许商用 |
| `reviewedBy` | 责任人（人工） |
| `reviewedAt` | 审查时间 |

缺失任一字段：记录进入 `quarantine`，不参与能力加载、索引、构建或验证。

## 3. 导入流程（受控闭环）

```text
外置原件（不入 Git）
   │  SHA-256 计算 + 回读校验
   ▼
SourceRecord（满足 §2 全部字段，人工批准）
   │
   ├── 提取结果（匿名化方法、grammar、决策规则）
   │        ↓
   │   MethodCard / ReferenceSet / Rubric / Benchmark（入 Git，必须含来源引用）
   │
   └── 无法满足准入 → quarantine/（不参与任何门禁）
```

- 人工批准（`reviewedBy` + `reviewedAt`）是硬前置，无批准不导入。
- 提取结果必须来源可追溯（`sourceRef` 指向 SourceRecord）。
- 许可不允许派生/模型输入时，即使有 SourceRecord 也不得生成生产内容。

## 4. 体积与膨胀门禁（P1-4 落地）

- 仓库总预算：**≤ 256 MiB**（当前 `.git` ~199 MiB，仍须收敛）。
- 单文件上限：**≤ 5 MiB**（超出必须外置或转引用）。
- 二进制准入门禁：新增二进制文件必须通过 `verify_asset_governance.py`（校验：大小、LICENSE 侧车、SHA-256 记录、来源）。
- 不引入 LFS 作为默认依赖；必要时按 Host Adapter 合同单独评审。
- 超预算/超限文件：拒绝提交，改走外置库 + SourceRecord。

## 5. 验证链（fail-closed）

- `verify_source_registry.py`（DL-KNW-004，替代 `verify_source_registry_v2.py`）：v3 SourceRecord 全量 schema 校验；缺任一字段 → 非零；`GOVERNANCE_GAPS>0` → 失败。
- `verify_license_coverage.py`：新增文件必须 SPDX 头或 `.license` 侧车；缺失 → 失败。
- `verify_design_lab.py`：任一必需验证器缺失 → `MISSING` 失败；失败不写 `.verify-chain-ok`。
- `verify_release_evidence.py`：无证据文件 / 无 exact-SHA 绑定 → 非零退出。
- 任何验证失败：不允许 E4 发布证据。

## 6. 隐私与权利

- 不读取、不提交：凭据、OAuth、token、私有会话、prompt/回复正文。
- 权利人禁止的用途即使有记录也不执行。
- 争议来源（`unknown`/`quarantine`）不进入生成上下文。

## 7. 例外与变更

- 例外必须写入 `reports/history/` 并由人工批准，注明原因与到期时间。
- 本政策变更走 PR + 独立复审 + exact-SHA CI。

### 例外清单（2026-08-14 批准）

| 资产 | 豁免 | 原因 | 条件 |
|---|---|---|---|
| `fixtures/domains/game-visual/assets/generated/*.gif`（6 个 CCTV lite-loop，8.4~11.8 MiB） | 单文件 5 MiB 上限 | minigame-runtime 生成资产，运行时依赖，可再生成 | 必须有 `.license` 侧车（已补）；计入总预算 256 MiB 门禁；若 minigame-runtime 改造为运行时生成则移出 Git |
