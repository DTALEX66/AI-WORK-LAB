# ADAPTER_POLICY — 适配器政策

- 版本：`1.0`｜状态：`ACTIVE`｜SSOT 角色：适配器契约

## AdapterRecord

```text
id / type(host|agent|tool|model) / mode
supportedObjects / capabilityScope / versions
requiredPermissions / secretHandling / networkPolicy
rightsDependencies / installPolicy / rollback
evidenceLevel / lastVerified / boundTreeSha
```

## 模式

`in-process`、`process-isolated`、`external-cli`、`external-local-api`、`external-provider-api`、`none`。

## 规则

- 所有外部适配器默认不执行；须经项目选择、明确授权和可回读证据才可运行；
- 产品契约不默认绑定任何 host/agent/model；
- 密钥只在用户本机环境配置；禁止入库、UI、日志、报告和截图；
- 未达 E3 不得写"已集成"；
- H3–Comfy bridge 未满足前置条件时明确为未启用。

## Open Design 双身份边界（2026-08-18，WORK-LAB 交接对齐）

- Open Design **client 期望态**（USER_GLOBAL 配置：MANAGE + apply_supported=false）由 WORK-LAB 控制面管理；
- DESIGN-LAB 只拥有 Open Design **capability**（模型/工具/资产生成参数），投影关系 = OBSERVE（只读）；
- DESIGN-LAB 禁止反向管理 Open Design client 配置（不写 client 状态、不申请写权限）；
- 本仓库 adapters/hosts/open-design 为 host adapter（E0），保持只读投影语义。

## 运行时入口（2026-08-18 实测）

- Open Design 宿主：D:/Programs/Open Design（Electron），CLI 内核 resources/open-design/bin/libexec/opencode/opencode.exe（opencode run / serve / export 可用，内置 free 模型）；
- Photoshop 2023：C:/Program Files/Adobe/Adobe Photoshop 2023/Photoshop.exe（COM + JSX 实测：建文档/文本层/保存可编辑 PSD）。
