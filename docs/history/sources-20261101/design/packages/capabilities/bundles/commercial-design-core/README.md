# Commercial Design Core

商业设计核心 bundle：面向商业/营销场景的可组合能力包。

## 包含

- 品牌视觉指导（brand-visual-director）
- 平面设计指导（graphic-design-director）
- 设计 QA 评论（design-qa-critic）

## 用法

通过 Open Design 插件体系加载（`open-design.json` 定义能力契约），
bundle 聚合多个 director 插件为统一入口。

## 边界

- 不包含模型/权重/素材（外置真源边界）
- 生成物写入忽略目录（`80-evidence/` / `.hermes/task-runtime/`）
