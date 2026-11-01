# R3-02/04 测试入口环境修复与审计

当前范围状态：**定向与完整本地回归通过（完整套件 1 项跳过不计通过）；整项 R3-02/04 不升级完成**。未提交、上传、修改全局配置或迁移用户数据。

## 已实施

- `scripts/run_python_tests.py` 与 `design-lab/scripts/run_test_isolation.py` 复用新 `src/design_lab/runtime/test_environment.py`；该模块调用现有 `resolve_paths`，不另建路径真值。
- discovery 之前先检查全部 temp/cache 路径，再创建目录。`TEMP/TMP/TMPDIR/XDG_CACHE_HOME/HF_HOME/TORCH_HOME` 指向项目内，子进程继承；进程退出上下文后恢复原环境与 `tempfile.tempdir`。
- 测试期间禁用 Python 字节码写入；直接 CLI 启动也在本地模块导入前禁用。环境 helper 在成功和异常退出时恢复原 `sys.dont_write_bytecode`。
- 空测试集或筛选不到模块返回 2，不再以 `ran=0, ok=true` 宣称成功；真实测试失败仍返回 1。
- 测试入口说明移除过期用例数和旧 MiniGame 路径，改为当前 lock/CI 命令。Adobe 两份活动说明改用 `.project-local/`，撤回只靠退出码/一次导出即可认 E3 的旧口径。没有移动旧 `.hermes/80-evidence` 内容。

## 实际证据

| 阶段 | 证据 | 结果/范围 |
|---|---|---|
| RED | [修复前结果](../../.project-local/task-artifacts/test-entry/red-20260906T185202997851Z/results.json)、[日志](../../.project-local/task-artifacts/test-entry/red-20260906T185202997851Z/focused.log) | 6 个用例中共 9 个断言失败；真实复现旧 temp 根、非法根仍执行、空选择仍返回成功 |
| GREEN | [最终定向结果](../../.project-local/task-artifacts/test-entry/green-20260906T185420020280Z/results.json) | 新 6 项 + 原路径 16 项通过；真实隔离入口随机顺序重复 2 轮，每轮 22 项通过；绑定源前后无变化 |
| 启动/异常补验 | [独立结果](../../.project-local/task-artifacts/test-entry/bytecode-20260906T185926550068Z/results.json) | 专用项目 fixture 使用源文件精确字节副本，真正 `__main__`、无 `-B` 启动两入口及空选择；零 pyc。context 初始 flag=False，成功/异常后均恢复 flag、cached temp 和环境 |
| 完整根入口 | [运行日志](../../.project-local/task-artifacts/test-entry/full-20260906T185503635278Z/root-suite.log)、[终态结果](../../.project-local/task-artifacts/test-entry/full-20260906T185503635278Z/results.json) | 756 项：755 通过、1 跳过；1065.884 秒。49 统一门与许可检查通过，绑定源前后无变化 |

初次编写的观测 fixture 对缺失 `XDG_CACHE_HOME` 直接取值导致 KeyError；之后把缓存环境显式设为项目内的错误候选根，修复前的正式 RED 因行为断言失败而非夹具报错。没有为测试通过改成接受旧根或零测试成功。

只读审查没有发现阻断性实现缺陷，提出“原驱动带 -B、未覆盖启动分支”的非阻断缺口；上述启动/异常补验针对该缺口真实执行，不把代码阅读当作运行证据。补验不代表独立安装包已通过，仍使用当前主环境 Python 3.13.14；Python 3.12/Linux/托管 CI 资格另验。

## 冻结源码与接续

审查及定向验证绑定：

| 文件 | SHA256 |
|---|---|
| `scripts/run_python_tests.py` | `c1127e1ebe16bcfe7b13b9d5571e93ef346c51717fcf4d3fd8a46d4ad84d532c` |
| `design-lab/scripts/run_test_isolation.py` | `73b1da257b785e06a120b3748a4db4dca23c6cfe77687c36f4f097526d22318c` |
| `src/design_lab/runtime/test_environment.py` | `c59f6b0d15ed2fa44fd386ad3cce8c540e24be0e7a6644fc81f9e99c6a2258e8` |
| `design-lab/tests/test_test_entry_environment.py` | `56c66fe72c60659589714217c3c987991e4d6ebf801bb2b9e4812e381c9f352d` |

完整检查命令为 `.project-local/task-artifacts/test-entry-20260907/check.py full`：真实根测试入口、统一门、许可检查均已终态，执行会话 **25917 TERMINAL / exit 0**，无需再轮询。结果观察时间 `2026-09-06T19:14:06.550744+00:00`。本切片按源文件绑定与独立分层口径登记正式账本；一项跳过没有被改为通过。此后 ComfyUI/H3 文档路径与旧 E3 口径修正另做定向门，不把它们冒充全量测试开始前的输入。

所有日志为 ignored 本地证据，换机不存在要报 MISSING。HEAD 仍为 `c4dccd58331bc4561eb89265283d924b7630d113`，不是完整未提交工作树快照。原生进程 scratch、Adobe/其他 Agent 入口、模型推理和 Human Gate 不因本修复获得通过状态。
