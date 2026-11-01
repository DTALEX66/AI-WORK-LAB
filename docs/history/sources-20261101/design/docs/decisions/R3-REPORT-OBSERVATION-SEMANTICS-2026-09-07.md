# 报告观察快照与完整性检查分离

基线 `a97e951b01d575b774d0ca81939cc365bcfec96a`。本地实现、25 项报告回归通过；不是当前 CI / 宿主 / 发布完成声明。

## 原始失败与设计

生成器原来把 HEAD、工作区状态和 tracked 数写入报告，然后 `--check` 每次取当前 Git 快照重建。仅提交生成物也会改变这些输入，导致十个文件漂移。无法靠反复生成→提交解决。

现在 index v3 保存 `gitObservation`，`--check` 用该观察快照及原生成时间重建内容，重新读取绑定输入并比对输入和输出 hash。真实 Git 路径还要求观察 SHA 在当前 HEAD 的祖先链上，缺失历史或无关历史不会视为有效观察；生成/检查期间的 Git 状态变化仍拒绝。

`--check` 明确输出 `scope=bound-input-integrity current-git-and-cloud=NOT_VERIFIED`。JSON 和 Markdown 都将 Git 内容标注为生成时观察。原 `fresh` 仅指生成时本地状态，不能读作当前云端新鲜度。

这是**检查职责的显式分离**，不是通过忽略 Git 差异宣称“当前一切通过”：此检查覆盖生成器绑定输入，不证明仓库每个未绑定文件均未改变，更不证明 CI、发布或软件实机状态。当前 HEAD/upstream/origin/main 仍需 Git 独立读回；云端状态需同 SHA API 证据。

## 已执行测试

在本项目 ignored runtime 下真实 `git init` 创建隔离夹具，通过命令局部 `-c user.name/user.email` 提供测试身份，不改全局配置。先提交夹具源码，再生成报告，再提交报告：

- RED：原实现因十个生成物漂移失败。
- GREEN：提交生成物后检查通过，报告仍诚实保留原观察 SHA。
- 修改绑定的任务定义文档，检查返回漂移。
- 其余既有报告测试（证据缺失、源码 hash 变化、错误 SHA、四轴防冒充、输出篡改）均通过；共 25 项。
- 真仓 generate 与只读 check 均成功。
- 聚合树统一门会话 81500 终态 exit 0，49 PASS / 0 FAIL；原始终态输出保留 `.project-local/task-artifacts/report-observation-20260907/unified-81500.log`。这是仓库门，不是宿主或模型推理。
- 完整 Python 测试由 `.venv/Scripts/python.exe -B scripts/run_python_tests.py` 启动，会话 14679 现已终态 exit 0：762 项、1062.010 秒，760 PASS / 2 SKIP。终态输出保存 `.project-local/task-artifacts/report-observation-20260907/python-14679-terminal.log`。这不是宿主实测；运行期间只新增文档/生成观察和提交，不改被测实现。

## 迁移、限制与回退

v2 索引没有观察字段，必须重新生成一次，不能自动猜测。显式 `snapshot=` 是既有夹具/调用接口，调用者拥有该参数真实性责任；CLI 不接受伪造 snapshot 输入。

在 `a97e951` 上重新生成时，旧 `c4dccd5` receipts 仍可显示 STALE_SUBJECT_SHA；不改原收据 SHA 或复制 PASS 来维持旧进度数字。后续需绑定真实新验证并追加证据。

需要当前 Git 状态时另行 `git status` / 明确 refs 读回；需要更新观察时主动运行 generate。本修改不把缺失的本地 ignored artifact 补成通过。回退代码和相应生成物即可，原 ledger / 历史收据未被修改。
