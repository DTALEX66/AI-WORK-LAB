# DESIGN-LAB：本地增量保全与源码/资料归属核对

这是只读与保全优先的检查表，不是磁盘清理命令。先记录现状，再取得与任务相称的变更权限。路径、diff、bundle 和日志可能含敏感信息，仅保存在已批准的私有位置，不自动提交上传。

## 1. 本项目先识别真实工作树

在已确认的仓库路径执行只读命令并记录结果：

```text
git rev-parse --show-toplevel
git rev-parse HEAD
git rev-parse HEAD^{tree}
git status --short --branch --untracked-files=all
git branch -vv
git worktree list --porcelain
git log -8 --oneline --decorate
git ls-files -z
git ls-files --others --exclude-standard -z
```

引号和花括号按当前 shell 正确转义。审查 remote 地址时去除潜在凭据，不把含 token 的 URL 写入可分享报告。检查未推送提交、staged/unstaged 的二进制变更以及子模块/LFS 是否有自己的未保存内容。

只在批准范围枚举 ignored 的高价值资料。不要递归哈希所有模型、node_modules 或整个磁盘；不要读取 .env/密钥正文。软件安装存在性从实际路径配置判断。

## 2. 保全要覆盖 Git 之外的工作

Git bundle 只能保存被包含 refs 可达的 Git 对象，不能替代未提交/未跟踪/ignored 资料、LFS 对象或子模块独立状态的备份。二进制补丁也不能代替所有未跟踪资产。

需要备份时：先选择获准私有输出目录，保存 refs、补丁和单独批准的源文件/设计包副本，并写内容哈希与恢复说明。运行中的 SQLite 通过已批准应用备份能力或一致性备份流程处理，不能复制一个正在写入的 DB 就宣称可靠备份。

逐项恢复试读后才进入修复，禁止将全部目录打包上传来图方便。

## 3. 三方/四方比较

| 对象 | 必查 |
|---|---|
| remote main | live SHA、tree、有效规则、最近实际 CI |
| cloud UI branch / open PR | head、base、真实 diff、checks、尚未合入语义 |
| local tracked changes | staged/unstaged、未推送 commit、现有测试与执行证据 |
| local-only assets / builds | 未上传高保真包、编辑源文件、运行态和实际安装 |

逐文件做 KEEP / PORT / EQUIVALENT / CONFLICT / LOCAL_ONLY / NEEDS_OWNER，不以时间较新自动覆盖内容，不把 main 不存在判为未完成。对于变化后的 main，重算差异，不硬套审计快照。

## 4. PDF / 资料是否漂移的判定

对已批准范围中的资料记录：精确路径、tracked/ignored、大小、来源和许可、用途、当前目录规则、是否运行期写入、目标逻辑根、迁移影响及回滚方式。

- 受控且合法的测试样例可以在 tests/fixtures，不能只因是 PDF 就移走。
- 学习资料原件、知识数据库、模型和转换输出按当前 source/data/runtime 根归属；不要把所有类型都塞到统一共享“资料库”。
- 商业设计源文件和交付资产按 DESIGN 权威留在项目批准数据区，不默认提交 Git，也不默认外传 AAOS。
- .project-local 是批准的项目本地输出路径之一；“物理上在项目文件夹内”不必然等于“进入源码版本库”。
- 历史约定 D:\All projects\资料库 等路径只作为核对线索，必须服从本项目当前目录配置和明确用途，不能盲移。

本次审计没有看到用户本地 PDF 的实际列表，不能把待核验项写成已确认违规。先给可审查迁移计划，再获得必要授权；本轮不批量移/删。

## 5. Green / 宿主环境

先读取安装身份、根目录、固定位置、进程、DB/worker/model 根和回滚能力。DESIGN-LAB 保留已有 Adobe/Comfy/H3/MiniMax 环境、客户素材和实际本地可用产品。任何候选都先隔离验证，不自动覆盖运行产品。
