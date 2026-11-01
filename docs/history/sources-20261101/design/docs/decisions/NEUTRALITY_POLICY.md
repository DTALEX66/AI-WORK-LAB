# NEUTRALITY_POLICY — 平台中立政策

- 版本：`1.0`｜状态：`ACTIVE`｜SSOT 角色：中立性契约
- 权威：本文件 + `product-manifest.json` 的 `neutralityPolicy` 一致

## 五维中立

| 维度 | 承诺 |
|---|---|
| 模型中立 | 无单一模型内建为产品能力；模型通过受控 Agent/media adapter 接入 |
| 风格中立 | 无 Apple/黑金/科技蓝/HUD/大师风格成为全局默认 |
| 领域中立 | 公共内核服务品牌/平面/UIUX/电商/编辑/包装/空间/展陈/3D/动效/视频/游戏视觉 |
| 平台中立 | 任意设计 AGENT 平台可作宿主/入口；产品契约不绑定默认 host/agent/model |
| 版本中立 | 不把任何宿主或工具的版本钉死为产品要求 |

## 宿主选择属于用户

- 产品 manifest **禁止** `primaryRuntime` 字段；
- 宿主选择（Open Design / Figma / Blender / ComfyUI / Adobe …）属于本地 profile 或项目级用户批准配置；
- 默认 fail-closed：未声明即不绑定。

## 边界

- Open Design 名称只允许出现在：历史、第三方 Host Adapter 标注、外部来源/兼容性引用；
- 任何活动 core 文档不得以旧名作为默认产品身份。
