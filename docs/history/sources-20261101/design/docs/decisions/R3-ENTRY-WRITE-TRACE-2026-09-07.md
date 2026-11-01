# R3-02 真实 CLI 生命周期与写入追踪

范围结论：Doctor 与 reconstruction CLI 的受控入口切片已实测；**R3-02 整项仍为 PARTIAL**。本记录不是全系统写入审计、语义拆图、Adobe 宿主验证或发布证书。

## 实际执行

使用本项目 Python 3.13.14，分别从仓库根和项目内专用 foreign-CWD 启动真实脚本；每个 CWD 又分别采用 `.project/paths.json` 默认根和显式 `PROJECT_LOCAL_ROOT` 子根。共四种组合，每种执行九次 CLI 调用，总计 36 次：

| 调用 | 实际应有结果 |
|---|---|
| Doctor `--paths --json` | 配置根一致，零 Python 写入事件 |
| analyze → reconstruct → verify | ANALYZED → RECONSTRUCTED_LOCAL → PIXEL_VERIFIED_DETERMINISTIC |
| verify `--cancel-after ANALYZED` → resume | CANCELLED / exit 1 → 完成 / exit 0 |
| 取消恢复后的 rollback | ROLLED_BACK；返回的删除目标逐个确认不存在 |
| 故意把预览期望 hash 设为零后 verify | FAILED / exit 1，原因必须是输出不匹配合同 SHA256 |
| 失败后的 rollback | 删除本轮生成的部分产物；保留输入 RIR 和未知旁置 sentinel |

输入是已有 `flat-64.png` 及显式四矩形 RIR，属于自有合成 fixture。流水线明确报告 `ORCHESTRATION_ONLY_NO_SEMANTIC_DECOMPOSITION`，像素通过不代表从任意图片自动拆解成功。

入口执行累计 34.972 秒，212 项检查通过。追踪器记录 Python 进程 PID/PPID、调用栈与 open/mkdir/rename/remove 等审计事件，并记录 subprocess 启动事件；不记录继承环境或子进程参数。路径事件包含操作尝试，不能全部当作成功落盘，实际产物及回滚删除另做读回。

后续独立读回 **111 项 PASS**：760 条 Python 路径事件在各自边界内；四组保留的 PNG 实际解码像素相同、SVG 字节相同；四个注入失败均为指定的 hash 拒绝。新的定向回归 **16 项 PASS、无跳过**，统一 **49 门 PASS**，许可检查 PASS。绑定的源文件在执行和回归后均未变化。本轮未重跑全部 Python 用例，统一门中的历史宿主文案不提升当前宿主资格。

## 原始证据

- [36 次执行结果及源文件绑定](../../.project-local/task-artifacts/entry-trace/20260906T184313916756Z/results.json)：SHA256 `33e3892128b3feec2be447ef213fcffd8d10b5b27150deae941897a52b333a9a`。
- [默认根、仓库 CWD 的渲染追踪](../../.project-local/task-artifacts/entry-trace/20260906T184313916756Z/configured-repo-reconstruct.trace.json)。同目录包含各次 stdout/stderr、trace 和回滚前文件 hash 清单。
- [独立读回与定向/统一验证](../../.project-local/task-artifacts/entry-trace-readback/20260906T184453743620Z/results.json)：核对所有源/证据 hash、四对保留的 SVG/PNG、实际解码像素、指定失败原因、回滚后的不存在性。最终结果以此文件为准。
- [执行脚本](../../.project-local/task-artifacts/entry-trace-20260907/run_trace.py)、[追踪器](../../.project-local/task-artifacts/entry-trace-20260907/trace_child.py)、[独立读回脚本](../../.project-local/task-artifacts/entry-trace-20260907/verify_trace.py)。脚本使用新时间戳目录，保留旧运行，不覆盖日志。

这些运行证据均为本地 ignored 文件。换机缺失应报 MISSING；不得从本文重建日志。本轮没有提交、上传或发布。HEAD `c4dccd58331bc4561eb89265283d924b7630d113` 不是完整未提交工作树，实际资格绑定源文件 hash。

## 本轮失败及修复

[首轮失败记录](../../.project-local/task-artifacts/entry-trace/20260906T184203081358Z/results.json)保留，SHA256 `86be4f77c48235eccd5986f08e718d06475970e259727eb4ad313fbe6c22af13`。Windows 的 `subprocess.Popen` 审计事件可提供 `executable=None`；追踪器错误地对其调用 `os.fsdecode`，导致渲染中断。最小真实 subprocess 调用复现该字段为 None。修复仅在追踪器保留 null 和 `NOT_SUPPLIED_BY_AUDIT_EVENT`，没有改产品渲染或放宽验收断言。后续全矩阵重跑在新目录完成。

追踪器不是安全边界。尤其 Windows 此事件没有给出可执行文件值时，不从调用器 PID 猜测实际子进程身份。

## 未完成边界与接续

- Python 审计钩子不是 Procmon/ETW。不能证明 native renderer、Adobe scratch、其他进程或全部旧根没有写入。
- 真实 UI、Agent/IDE 入口和 Adobe 产品桥仍缺同等级写入追踪；不读取 Agent 私有配置或会话来补证据。
- 四个共享/专属外置输入根未写入、未全盘扫描。本测试只证明被测入口的项目任务数据路径，不授予仓外迁移权限。
- 没有迁移用户数据或旧 DB。测试 rollback 仅删除本轮夹具产生的明确产物；成功样例、原输入和失败日志保留。
- 产品服务/工作台尚未实现的入口不能预先宣称已验收。后续需将本矩阵接到这些真实入口，而非重复测试底层 atomic writer。
- 当前 CI 触发本地变更、托管 CI、发布与远端读回独立验收。知识迁移继续延后；Human Gate 未签署。

下一步应继续实际缺口：项目启动/环境入口与 Adobe 正式桥的路径传递，以及模型加载/推理；不因本文产生而把所有规范化任务置为完成。
