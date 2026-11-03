# AIWORKLAB / AI-WORK-LAB

> **WORK-LAB + DESIGN-LAB 已合并为本项目 AIWORKLAB / AI-WORK-LAB。**
> 当前状态、能力、迁移去向与未完成项**只有一个入口**：
> **[PROJECT_CURRENT.md](PROJECT_CURRENT.md)** — 先读它，再读其他任何文件。
> 项目级执行规则见 [AGENTS.md](AGENTS.md)，执行边界与授权沿革见 [INTEGRATION_POLICY.md](INTEGRATION_POLICY.md)。

本仓库是本地融合后端：统一信封 + 统一存储 + 只读验收门，把 WORK-LAB 的工作循环与 DESIGN-LAB
的专业视觉智能接在同一套对象和合同上。它不是一个"把两个旧应用塞进两个标签页"的界面工程，
前端（STITCH）尚未做，也不在本轮范围里。

## 五分钟跑起来（本地，不联网）

```bash
# 1) 初始化工作区（幂等：只写一个"归属项目"标记；标记已存在就一字不改，也不碰别的文件）
python -m backend --init

# 2) 起后端：token 从 stdin 读，不进命令行、不落盘。缺这一步标记时服务不会自己造工作区，
#    而是回一条 WORKSPACE_NOT_INITIALIZED 的 json 与 next_action（这是新克隆上的第一步）
python -c "import secrets; print(secrets.token_hex(32))" | python -m backend

# 3) 真实 HTTP 启动探测：统一面 + 兼容面逐个路由读回，打印一条 json 判定
python scripts/boot_probe.py

# 4) 顶层入口防漂移：根入口引用的路径与数字，逐条与寄存器现值比对
python scripts/check_project_current.py --check

# 5) 全量回归（本机约 14 分钟）
python -m pytest tests/unified tests/legacy -q
```

Windows 上本仓自带解释器在 `.venv\Scripts\python.exe`；把它替换掉上面每一行的 `python` 即可，
不要假设 `python` 在 PATH 里。

## 权威在哪里（不要在这里找状态）

| 想知道 | 去看 |
|---|---|
| 现在成立什么、还差什么 | [PROJECT_CURRENT.md](PROJECT_CURRENT.md) |
| 能力族与验证状态 | `migration/capability-family-register.csv` |
| 验收子句逐条结论 | `migration/task-acceptance.csv` |
| 来源仓每个文件的去向 | `migration/source-coverage-work.csv`、`migration/source-coverage-design.csv` |
| 端点面实测 | `migration/route-surface.csv` |
| 阻断与延期 | `config/blocker-register.json`、`migration/deferral-register.json` |
| 逐轮实测与独立复审入口 | `docs/CODEX-AUDIT-ENTRY.md` |

这些表由 `scripts/` 下的 `build_…` 生成器现算，数字一律现算，不手抄。

### 同一段路径文字，可能属于四个不同的根

融合仓里最容易被读错的东西是路径：一个不带前缀的字符串到底该在本仓磁盘上解析，还是指来源仓、
统一归档或本机产物？逐类的解析根如下，读之前先对号，不要拿本仓的目录树去验证血统列。

| 你读到的位置 | 它解析到哪个根 | 现在还在不在 |
|---|---|---|
| 正文与寄存器里的仓内路径（`backend/`、`docs/`、`scripts/`、`tests/` 等开头） | 本仓根 | 在；`scripts/check_project_current.py --check` 逐条要求存在，缺一条就红 |
| 能力族登记的「拟模块边界」列 | **不是磁盘路径** | 那是来源任务表逐字带来的计划边界；找实现看「当前实现位置」与「验证证据」两列 |
| 来源覆盖登记与权威索引里的来源侧路径列 | 来源仓根（WORK-LAB / DESIGN-LAB） | 只作血统。原件字节在本仓 `docs/history/` 的历史区内（按 `<来源仓>/…` 分层），权威原件在 `docs/authority-202610/`，摘要逐条登记；两个来源仓按计划会被删除 |
| 归档对账登记的 `archive_path` 列 | 统一归档根（本机另一处，本轮只读） | 不复制第二份；其中 694 个正文对象已按摘要进 `docs/history/` 的对象库区 |
| `.project-local/` 开头的产物路径 | 本机，Git 不跟踪 | 克隆里没有。被寄存器点名的那份必须留下——清理判据不是大小而是"有没有被点名"，见 `docs/CODEX-AUDIT-ENTRY.md` §15.24 第十一段 |

## 仓库布局（顶层每个目录都在这张表里，检查器会守住这条）

| 目录 | 是什么 | 属于 |
|---|---|---|
| `backend/` | 融合组合根：统一信封 + 兼容面委托 | 现行代码 |
| `packages/` | 跨域公共合同与能力内核（`contracts` / `capabilities` 等） | 现行代码 |
| `domains/` | 两个域的现行实现：`work/`（WORK 工作循环）与 `design/`（DESIGN 设计智能，含随包资源） | 现行代码 |
| `design-lab/` | DESIGN-LAB 时期的 `config/` 与合同文件（含重建模型注册表等运行期读取的配置），不是整仓副本 | 现行配置，历史外形 |
| `integrations/` | 外部工具与宿主 Adapter 的连接面 | 现行代码 |
| `apps/` | `workbench` 兼容壳与品牌件（STITCH 前端**未做**） | 现行代码（壳） |
| `scripts/` | 生成器、验收门、探测、隔离安装、顶层防漂移检查 | 现行代码 |
| `config/` | 阻断登记、适配器注册表等机器可读配置 | 现行配置 |
| `tests/` | 统一面套件 `tests/unified` 与迁移来的一般回归 `tests/legacy` | 现行测试 |
| `migration/` | 全部去向/验收/能力/路由寄存器（由生成器写，不手改） | 登记 |
| `research/` | 迁入的研究资料与 `RESEARCH-INPUTS.json` 合同 | 登记资料 |
| `docs/` | 审计入口、当前状态、`authority-202610/` 置顶原件、`history/` 历史与归档区 | 文档 |
| `vendor/` | 随包第三方件 | 惰性第三方 |
| `workspace/` | 运行期工作区（被 Git 忽略，本机数据） | 运行产物 |
| `AI-WORK-LAB_HANDOFF_20261029/` | 本轮任务包原件（逐字节入仓、逐份摘要登记） | 历史原件 |

一条口径：`docs/history/sources-20261101/` 与 `docs/authority-202610/` 里的是**来源仓历史原件**，
按字节保真保存——不补 SPDX 头、不改行尾、不重排内容；本仓自研代码（`backend/` `packages/`
`domains/` `integrations/` `apps/` `scripts/` `tests/` `config/`）才要求 SPDX 头。

## 边界（如实，不夸大）

- 本轮为本地执行：不上传、不部署、不发布；系统级出站隔离**未被证明**。
- 真实宿主写入、模型推理、真实私有数据迁移、真人专业验收签字仍是 `NOT_RUN`，
  按 `docs/CODEX-AUDIT-ENTRY.md` §5 与 `migration/deferral-register.json` 记录，不拿合成回执冒充。
- 命令、日志、数据库与临时夹具只落 `.project-local/`（Git 不跟踪）。
- `D:\All projects\Project Archiving` 是统一归档原件，**只读**；不向归档反向清理。
