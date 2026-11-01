# Open Design Host Adapter（DL-ADP-OD）

Open Design 实现收敛于此目录；公共能力目录保留中性源定义。

```text
Neutral Capability Contract
→ Open Design Projection Generator (verifier/generate_open_design_adapter_indexes.py)
→ open-design.json（projections/）
→ Open Design Adapter Installer (installer/install_op_expert_suite.py)
→ 用户批准的 Host Profile（local-profile）启动
```

## 目录

- `adapter.manifest.json` — 适配器清单（status=declared, evidenceLevel=E0, supported=false）
- `installer/` — 安装器（install_op_expert_suite.py）
- `verifier/` — 验证器（verify_open_design_host_adapter.py）+ 投影生成器（generate_open_design_adapter_indexes.py）
- `projections/` — Open Design Manifest Projection（atoms/bundles/scenarios/plugins，指向中性能力目录）
- `expert-suite/` — Open Design 专家技能套件（skills/*）
- `schemas/` — 适配器专用 schema 说明
- `tests/` — 平台中立性测试（DL-ADP-OD-004）
- `evidence/` — 适配器证据（E0 声明；E3 需真实运行后取证，禁止伪造）

## 平台中立（DL-ADP-OD-004）

- 产品 Manifest 无默认 Host；`primaryRuntime` 禁止。
- Open Design 不出现在公共产品身份字段。
- 公共对象 Schema 不依赖 Open Design API；本目录是 Open Design 实现的唯一所有者。
- 安装器只能通过用户批准的 Host Profile 启动。

## 边界

- 未启动 Open Design Host / 运行时；status=declared、evidenceLevel=E0、supported=false（DL-H3 冻结同款诚实声明）。
- Open Design 作为第三方独立 Host，不得反向依赖公共 Core。
