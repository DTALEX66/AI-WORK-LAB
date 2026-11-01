# DESIGN-LAB 个人产品整体审计与修复 — 2026-10-07

## 结论与验收边界

整体判定 **PARTIAL**。本次已修复个人入口、统一 UI、刷新状态、安装资源和备份恢复缺陷；这些是本机 E2 受控运行证据。项目仍没有完成真实宿主生产链路、独立人工 Jury 和发布级复现，不能标为成熟商业产品。

用户本次授权：按成熟落地的商业级个人产品审计整体项目，有问题修复；个人使用，不增加防护令牌/密钥软件。没有新增生产依赖、安全产品、账号体系或第二前端。官方入口自动本机连接；已有底层服务调用约束保留为内部机制，用户无需复制令牌。

## 当前对象与权威

- 权威：`AUTHORITY.md`（DL-AUTHORITY-2026-09-18-R2）、`.project/governance/authority-index.json`、当前 FINAL TaskPack、`design-lab/config/task-ledger-r3.json`。
- 本地 HEAD：`1d18ae80d995a705d0de5341cd5c76b362c3e532`；分支 `qoder/designlab-picker-autoselect-20261007`，开始即有未提交 UI 和报告修改。
- 实时公共 GitHub main：`fc03a3033e900a8066d863a223636cc68804c4fa`；open PR 0；Canonical Verify run `37602613560` completed/success。对应 workbench-e2 artifact 存在且未过期（仅核对归档元数据，未冒充内容验收）。这个成功属于该 main SHA，不属于本次修改。
- branch protection：UNKNOWN（401）；fetch `.git/FETCH_HEAD` 被拒，没有提权。用本地 origin/main 对象与 live SHA 对照后只读 archive 取证。
- QODER handoff 是审计输入，不是顶层权威。报告 B 和 handoff 在较旧本地主检出缺失，但最新 main 实际存在，不能据旧检出宣称整个项目缺失。
- 当前产品规定 frontend 为 `apps/workbench/` 的 strict TypeScript / Vite 浏览器工作台。桌面原生外壳需要明确需求与 ADR；本次没有擅自替换技术路线。

## 实施的修复

| 问题 | 修复与限制 |
|---|---|
| 默认首页仍走旧单页布局，路由页进入另一套 UI | 所有页面统一 AppShell；空 hash 工作台也挂在同一侧栏/顶部中。保留原设计表单 ID 和调用链。 |
| 官方启动要求复制短期令牌 | `workbench` 默认同源自动连接；终端不输出令牌，页面刷新自动重连。`--manual-connect` 只用于兼容。未落盘连接凭据。 |
| 移动侧栏关闭后仍可能进入键盘焦点 | 关闭抽屉使用 inert，打开/关闭恢复焦点，840px 和390px检查。 |
| 刷新后项目选择丢失 | 只在 localStorage 保存项目 ID，并对服务端列表校验；不存凭据。 |
| 新建项目可能重复提交 | 提交锁与按钮状态，失败后恢复可重试。 |
| 素材刷新清除参考图选择 | 重新构建 picker 时保留已选 ID，避免简报无意提交0参考图。 |
| 小屏能力库面板和过滤框被裁切 | 过滤框允许收缩和换行；复跑真实浏览器溢出检查。 |
| 能力库源码工作但安装包缺数据 | 精确打包4份只读能力库输入，installed-site 能读回60条，不打包整个 vendor 或运行目录。 |
| Windows 长路径错误显示为通用服务故障 | 明确 PROJECT_PATH_TOO_LONG 并提示使用短目录；不是支持任意长路径。 |
| SQLite 原样复制可能漏 WAL 已提交数据 | 使用 SQLite backup API 做一致性数据库快照，排除 WAL/SHM。 |
| 备份失败会破坏原归档/归档可能包含自身 | 先写临时归档、验证后 replace；拒绝写入被备份成员内。 |
| 迁移恢复后素材索引仍指向旧绝对路径 | 归档记录源 local root；恢复时仅重定位 live artifact.path，实际图片导入→迁移→读回已测。旧签名执行记录不改写，迁移执行需要重新规划。 |
| 恢复中途失败可能留部分覆盖 | 先解压验证暂存，再安装；应用层异常恢复已替换文件。不是断电时跨文件原子事务。 |
| 测试写系统临时目录引发大量拒绝 | bound runner 将本次测试 TEMP/TMP 限定在项目 `.project-local/task-runtime/`，不修改系统配置。 |
| 量化审计拒绝未提交构建 | 增加显式 UI_AUDIT_LOCAL_BUILD=1，仅绑定本地 bundle hash 和 LOCAL_WORKTREE；默认已提交构建约束仍保留。 |

本地落后 main 的相关 UI 响应形状检查、三型失败态和能力库投影已带回。原有 SUPPLY-CHAIN-REPORT 修改与未跟踪 UI 报告保留。没有 reset/clean/commit/push/merge；未清理真实项目、未知 worktree 或旧服务。

## 验证

- strict TypeScript 类型检查、Vite生产构建、Node smoke/AppShell/21 seam响应形状覆盖：PASS。
- 51项定向回归：50通过、0失败、0错误、1跳过。跳过是源码模式下没有已安装包资源；另用安装态3项全部通过、0跳过补验证。
- 真实浏览器设计纵切覆盖图片导入、参考简报、方向、绑定、修订、刷新/读回；个人入口覆盖不手填凭据连接、项目保留和移动导航：PASS（E2）。
- 溢出门：1440/1024/390px，12路由，PASS。量化 UI：390/1280px，26 scopes，0 hard violations；本地构建哈希已绑定，非人工视觉验收。
- 备份恢复15项：包括WAL快照、原归档保留、迁移后真实PNG读回、恢复异常回退，PASS（合成项目数据）。
- 初次全量：1908 tests /108 failures /279 errors /11 skips，FAILED，日志 bound-suite.log。
- 调整项目内临时目录后全量：1914 tests /107 failures /52 errors /11 skips，FAILED，日志 bound-suite-final.log，绑定 full-final-run.json。这次全量在最后的UI mock兼容修复前执行，不能声称它覆盖之后全部修改。
- 最后UI mock兼容修复后的扩展定向回归：65 tests /0 failures /0 errors /1 skip，64通过；targeted-final-v3.json。安装态另3项全部通过、0跳过。。
- 独立安装副本：复用既有项目依赖，60条能力记录读回、3项启动/重启读回检查，PASS；最终wheel哈希见 installed-proof.json。

全量失败分层：严格路径解析已独立复现 WinError5；多个reparse/rename/fixture调用也被拒。现有.venv持续输出外部uv解释器位置警告，影响要求机器stdout/stderr纯净的检查。重建流程存在许多上述失败的下游断言，不能据此声称功能正确。旧ledger的源码证据哈希也因本次改动失效，不能重写历史证据冒充新验收。三个UI mock兼容失败已修复并单独复跑；其余失败保留在 failure-inventory.json，不因部分修复从总数中扣除，剩余未逐项证明的失败仍需在正常执行环境定位。

证据目录：`.project-local/task-artifacts/personal-product-audit-20261007/`。截图：`.project-local/task-artifacts/personal-browser/personal-home-desktop.png`、`personal-home-840.png`、`personal-home-390.png`。

## 尚未达到的产品成熟条件

1. 真实 brief→Photoshop/Illustrator 原生可编辑产物→重开读回→失败与回滚尚未在本次执行。浏览器通过不是 E3 宿主验收。
2. 质量 Jury、rights 与 preflight 的人工判断没有代填；模型许可队列与硬件资格不因展示在能力库而自动通过。
3. 页面里已声明没有后端的能力仍是未接通状态；不编造功能、评分、生产成功或团队协作结果。主设计纵切是受控运行，不代表全部设计域交付成熟。
4. 本次 wheel 是本地安装副本验证，复用既有 .venv 依赖，不是完全清洁安装、发布、升级和持续复现，不是 E5。
5. 备份期间应停止生产写入；数据库快照不等于数据库与全部素材的跨文件全局快照。恢复或迁移原生执行时应重新规划；旧归档没有源路径元数据时拒绝冒充跨根恢复成功。
6. 全项目门禁的失败、required skip 或 UNKNOWN 必须保持显式，不以本次 UI 局部通过覆盖。

## 使用与回退

启动：`python -m design_lab --project <设计项目目录> workbench`。默认打开本机工作台自动连接，刷新重连；`--no-browser` 只打印本机 URL。

本次替换前源码备份在证据目录的 `before/`，初始文件哈希见 `before/manifest.json`。后来纳入的备份与测试文件也逐个备份。需要回退时只对这些明确文件审阅后恢复，不批量 checkout、不覆盖用户原有修改。运行产物不提交。

最终本地 wheel SHA-256：`508faee4abc740a5e85a2b8245c013492228f8eecfd62f9bc4900a34c1db78cf`；最终 bundle SHA-256：`3e3717c22cb82e1f469fa5422ab4ae7af5f719f2c2949c98184e926c173e1614`。
