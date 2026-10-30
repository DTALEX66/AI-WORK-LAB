# AI-WORK-LAB 本轮融合执行策略（LOCAL_ONLY_NO_REMOTE_ACTIONS）

版本：2026-10-29 R1（由本地后端融合执行任务在 P0 写入）
依据：`AI-WORK-LAB_HANDOFF_20261029/02_ZCODE_本地后端闭环提示词.txt` §0 与
`09_任务分期与验收.json`；用户 2026-10-29 会话内补充决定见文末。

## 1. 执行边界

| 项 | 状态 |
|---|---|
| 远程仓库写入（push/force-push/远程分支/标签/PR/Release） | **禁止**；2026-10-31 owner 会话内决定对**首次上传**与**仓库描述更新**放行（见 §6），force-push / 改历史 / PR / Release 仍禁止 |
| 云构建 / 远程 CI / 远程部署 / 发布 | **禁止**（§6 的首次上传不含云 CI 触发、部署或发布） |
| 任何渠道上传项目、数据、日志、任务包（API/网盘/邮件/消息） | **禁止**；§6 只放行 Git 首推到 owner 自有远程仓，日志与运行库仍只落 `\.project-local\` |
| 自动 clone/fetch/pull | **禁止**（§6 不含 fetch/pull：远程仓当时为空，无合并来源） |
| 包下载 | 默认禁止；**用户 2026-10-29 会话内明确改为“缺工具可以下载”**（见 §4） |
| 遥测 / 崩溃上报 / 云索引 / 远程执行 / 自动 Agent 派发 | **禁止** |
| 本地 loopback HTTP（127.0.0.1 绑定） | 允许（统一后端验证必需） |
| 本地分支创建 / 目标仓源码修改 / 本地验证 | 允许 |
| 默认 commit / 合并 main / 重写历史 | **不执行**（工作树用基线清单+SHA-256 绑定）；**首次 commit** 由 §6 放行，重写历史仍不执行 |
| WORK-LAB、DESIGN-LAB 来源仓 | **只读**（状态、冻结字段、历史、本机作品不得改动） |
| AAOS、ASTRYN | 不在写入范围 |
| E:/F: 盘 | 无精确路径授权不访问 |

## 2. 出站隔离声明（如实记录，不夸大）

- 本轮执行策略禁止联网外传；所有 Git 操作均为本地。
- **未证明系统级出站隔离**：未安装/未配置防火墙规则、进程沙箱或容器隔离。
- 执行本任务的模型为云端模型（ZCode 会话模型），发送给模型的上下文可能离开本机；
  提示词与 Git pre-push hook 不能阻止该通道。此限制如实登记，不宣称已消除。
- ZCode 客户端自身的遥测/索引行为无法在本轮完全确认关闭；已确认的边界：
  本任务未主动调用任何网络上传命令，未执行 git push，未创建远程资源。

## 3. 防误操作 pre-push hook

状态：**待设置**（设置前先检查并保全本仓现有 hooks 与 core.hooksPath；只在本仓内变更，
提供恢复记录；此措施仅防误操作，不代替出站隔离，不覆盖 API 上传）。

## 4. 用户会话内补充决定（2026-10-29，优先于任务包默认）

1. 用户确认 `D:\All projects\DESIGN-LAB`、`D:\All projects\WORK-LAB` 本地内容**多于云端提交**
   → 保留本地现状为迁移来源，不回退到历史锚点；锚点 9882a89c（DESIGN）/ a8cc2fb（WORK）
   仅作研究参照，本地增量（锚点→HEAD 差异 + 未提交改动）单独成册。
2. 用户指认共用外置库索引位于 `D:\All projects\OS External Configuration`
   （00-registry/project-tool-index.yaml 等）→ 已勘察登记。
3. 用户明确「缺工具可以下载」→ 允许为缺失工具执行**最小必要下载安装**；
   每次下载记录工具名、版本、来源、用途。核心后端仍优先标准库与本地已有依赖。

## 5. 数据边界

- 真实凭证、原生认证库、私有会话、API key、模型权重、用户作品：不入 Git、不复制。
- 数据迁移只用：用户批准的工作区副本、既有公开样例、合成夹具。
- 审计与运行产物只落在 `D:\All projects\AI-WORK-LAB\.project-local\`（非云同步目录）。

## 6. 用户会话内决定（2026-10-31）— 首次上传与仓库描述更新

Owner 原话（逐字）：「完成后上传到仓库  更新描述」。这是会话内指令，无外部任务包、无源哈希，
按 §4 的先例登记；本节只**定点放行**下列三个动作，其余边界不变。

放行的动作：

1. 对目标仓做**首次 commit**（此前 HEAD unborn，候选全部是未跟踪文件）。
2. 首次 **push** 到 owner 自有且当时为空的远程仓 `DTALEX66/AI-WORK-LAB`（HTTPS/SSH 由本机
   既有 GitHub CLI 凭据提供，本仓不读取、不打印、不复制任何凭证明文）。推送对象是当前工作分支
   `integration/local-fusion-20261029`，不创建 PR、不合并、不打标签、不发 Release。
3. 更新该远程仓的**仓库描述**（GitHub About），如实写明「融合候选、QODER 自测完成、
   待 Codex 独立复审、不是已发布产品」。

不放行（继续禁止）：`--force` / `--force-with-lease`、改写已推送历史、`git fetch/pull/clone`、
云 CI 触发、部署与发布、把 `.project-local\` 内的数据库/日志/证据/任务包上传到任何渠道。

防误操作 hook 的处置：pre-push hook **不删除、不用 `--no-verify` 绕过**。做法是按 SHA-256
登记后把原文件临时移出 `.git\hooks\`，完成这一次授权推送后再逐字节放回原位并复核摘要——
即 §3 的「防误操作」作用在推送之后立即恢复，本节不把它当作出站隔离证据。

推送前的机器可读审读（逐文件现算，数字只写在证据 JSON 里，不手抄）：
`.project-local\push-20261031\prepush-hazard-scan.json`（凭证形态命中数）、
`public-exposure-scan.json` 与 `personal-identifier-detail.json`（个人标识与真实邮箱）、
`candidate-before-doc-edit.json` / `candidate-after-regression.json`（候选摘要与逐文件差）、
`push-state-*.json`（分支、提交、树、hook 摘要、远程回读）。

公开性后果（如实声明，不轻描淡写）：该远程仓可见性是 **PUBLIC**，首推后候选内容可被公网读取与
索引。判定依据是逐文件扫描而非印象：凭证形态 0 命中；真实邮箱 0 个（首轮把
`…@1440.png` 这类文件名误判为邮箱，已在第二轮过滤）；用户目录绝对路径只出现在
`config/adapter-registry.json` 与 `packages/contracts/schemas/workflow/software-update-postflight.schema.json`
两处，而这两个文件在 owner 自有的公共来源仓 WORK-LAB 中已被 Git 跟踪且与 HEAD 无差异，
因此本次上传没有新增该标识的暴露面。两个来源仓同为 PUBLIC。

仍然成立且未被本节改变：系统级出站隔离未被证明；云端会话模型的上下文可能离开本机；
来源仓只读；E:/F: 盘不访问；真实用户数据迁移、真实宿主写入、模型推理、外部执行器资格、
STITCH 前端、真人签字仍按 `docs/CODEX-AUDIT-ENTRY.md` §5 的 NOT_RUN/BLOCKED/DEFERRED 记录。

