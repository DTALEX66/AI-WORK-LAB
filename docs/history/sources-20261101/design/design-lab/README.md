# design-lab/ — DESIGN-LAB 能力层

这里是 **DESIGN-LAB（设计实验室）** 的能力层主目录：面向任意设计 AGENT 平台的中立设计能力与视觉质量增强层。

> **Agent-platform-neutral design intelligence and production laboratory for professional visual design with commercial production preflight and editable delivery. Host-native; no default host, agent, or model binding.**

## 权威文档（SSOT）

```text
docs/PRODUCT_DEFINITION.md    ← 唯一产品定义
docs/ARCHITECTURE.md          ← 技术架构
docs/BOUNDARY_CONTRACT.md     ← 职责边界
docs/NEUTRALITY_POLICY.md     ← 平台中立
docs/EVIDENCE_POLICY.md       ← 证据政策
docs/ADAPTER_POLICY.md        ← 适配器政策
docs/OBJECT_MODEL.md          ← 核心对象模型
docs/USER_MODES.md            ← 五类用户/五种模式
docs/ROADMAP.md               ← 路线图
```

## 机器可读 SSOT

```text
design-lab/config/product-manifest.json   ← 产品 manifest（design-lab/product-manifest/v1）
design-lab/config/capability-status.json  ← 能力状态
design-lab/config/object-model.json       ← 13 核心对象
integrations/adapter-registry.json        ← 适配器注册（defaultBinding=none）
```

## 验证入口

```bash
python design-lab/scripts/verify_design_lab.py        # 全验证链（统一入口）
python design-lab/scripts/verify_identity_gate.py     # 身份边界 gate
python design-lab/scripts/verify_product_manifest_v3.py
python design-lab/scripts/verify_runtime_contracts_v3.py
python design-lab/scripts/verify_visual_scoring_v3.py
python design-lab/scripts/verify_source_registry.py
python -m pytest design-lab/tests/                    # 单元 + fixture 测试
```

## 目录

```text
core/           对象、契约、政策
intelligence/   intake、direction、system、critique
atoms/          可测试小能力
bundles/        公开复合体（commercial-design-core / visual-quality-core / production-handoff）
scenarios/      端到端视觉设计场景
domain-packs/   专业领域包
quality/        Rubric、Jury、视觉回归
production/     Preflight、Handoff、Provenance、Rollback
knowledge/      受治理来源与方法（sources/curated/derived/methods/standards/registries）
research/       风格谱系、视觉基准、领域研究、实验记录
evals/          测试 fixtures 与证据索引
schemas/        中性 JSON schemas
config/         checked-in 中性注册表
scripts/        确定性生成器/验证器
templates/      模板
assets/         资产
adapters/       host/agent/tool/model 适配器（无默认绑定）→ 见 ../integrations/（DL-DIR-MIG-R1 迁出）
```

## 适配器

适配器目录已随 DL-DIR-MIG-R1 迁出 `design-lab/`，现位于仓库根 `integrations/`（host/agent/tool/model 适配器，无默认绑定）：

- `integrations/hosts/open-design/`：Open Design host projection（F1 兼容层）
- `integrations/hosts/adobe/`：Adobe PS / Illustrator E0 合同 + reconstruction
- `integrations/generators/`：ComfyUI / MiniMax H3 等生成器适配
- `integrations/mcp/`：MCP 适配
- `integrations/adapter-registry.json`：注册表（defaultBinding=none）

## 证据纪律

- 未达 E3 不写"已集成"；静态文件只证明 E1；
- 旧树 E3 证据不误用于新树（见 capability-evidence-index.json 的 requiresRequalification）；
- 外置资料库 `D:\All projects\Design assets` 仅登记，不复制、不索引原件。
- 外置依赖/工具链/缓存配置根：`D:\All projects\Design External Configuration`（依赖清单见其 `EXTERNAL_DEPENDENCIES.md`，不提交 Git）。
