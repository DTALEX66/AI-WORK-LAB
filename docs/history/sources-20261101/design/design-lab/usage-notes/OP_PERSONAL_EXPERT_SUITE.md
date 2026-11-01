# OP 个人专家套件 — 官方安装与说明

## 是什么

把本仓库的 UI/UX 五黄金案例方法、设计系统、设计技能与方法论专家转成 **Open Design Personal Skills**（`source: user`）与 Personal Design Systems，使 OP 在当前个人 Workspace 的所有项目中都能按这些方法工作。

## 已配置的资产

套件包含 **15 个 Personal Skills** 与 **3 个 Personal Design Systems**。完整清单以仓库为唯一权威：

- 技能：`integrations/hosts/open-design/expert-suite/skills/<name>/SKILL.md`（15 个）
- 设计系统：`design-lab/design-systems/<name>/DESIGN.md`（3 个）

技能/系统均保留 OP 原生 frontmatter：`name`、`description`、`triggers`、`od.mode`、`od.category`、`od.upstream`。

## 安装（Open Design 0.19+ 官方 Personal Skill 流程）

先启动 Open Design，然后从仓库根目录运行：

```bash
python design-lab/integrations/hosts/open-design/installer/install_op_expert_suite.py
```

脚本会自动：

1. 从 OP 的 `logs/web/latest.log` 发现当前 Web sidecar；
2. 调用 `GET /api/workspace/directory` 选择当前 Personal Workspace；
3. 调用带 Workspace 身份的 `GET /api/skills` 检查现有技能；
4. 对缺失项调用 OP 官方 `POST /api/skills/install`。

默认对**正文与仓库一致的技能**执行 `skip`，不会擅自覆盖。正文与仓库不同时，仅当该技能归属与本仓库一致才刷新，否则失败关闭、拒绝覆盖用户自有内容。仓库技能源更新后，显式运行：

```bash
python design-lab/integrations/hosts/open-design/installer/install_op_expert_suite.py --refresh
```

`--refresh` 也只调用 OP 官方 `DELETE /api/skills/:id` 和 `POST /api/skills/install`，不直接修改数据库。

只预览动作：

```bash
python design-lab/integrations/hosts/open-design/installer/install_op_expert_suite.py --dry-run
```

## 验证标准

当前 Personal Workspace 的 `GET /api/skills` 应包含 15 个 Personal Skills，`GET /api/design-systems` 应包含 3 个 Personal Design Systems，并满足：

```text
source=user
mode=design-system
hasBody=true
```

OP 会为每个 Personal Skill / Design System 自动管理归属记录；安装脚本不直接操作该内部记录。

## 存储位置

- 仓库源（唯一权威）：`integrations/hosts/open-design/expert-suite/skills/<name>/SKILL.md` 与 `design-lab/design-systems/<name>/DESIGN.md`
- OP 桌面用户技能目录（由 OP 官方 API 管理）：位于当前激活 namespace 的 `data/skills/<name>/SKILL.md`（namespace 动态发现，不绑定特定版本目录）
- 项目级技能：`<项目cwd>\.od-skills\<name>\SKILL.md`（仅该项目可用）

## 在 OP 中使用

在 OP 对话里直接描述技能场景即可，例如：

- “用移动端任务流方法设计一个预约小程序。”
- “用 B2B 后台工作台方法重构这个管理控制台。”
- “使用 uiux-commercial-light 设计系统统一这组页面。”

## 边界

- 不直接复制或修改 OP 内部数据库；
- 不伪造 Workspace binding；
- 不依赖某个固定的 0.19.x 安装版本目录或端口（namespace、端口、模型基线均动态或可配置，不硬编码）；
- Personal Skill / Design System 文件和归属由 OP 官方 API 创建、更新和删除；
- 仓库是知识源，运行时由官方安装器同步。
