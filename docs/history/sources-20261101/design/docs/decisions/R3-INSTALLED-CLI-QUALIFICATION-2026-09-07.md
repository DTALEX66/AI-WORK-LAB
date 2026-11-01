# 安装后 CLI 与项目元数据持久化资格验证

状态：TESTED_LOCAL（限 CLI 元数据与 SQL 资源）；R3-09 / DL-R4-009 仍 PARTIAL。

## 输入与范围

- 基准 HEAD：`709bf3e72ce21c29b9f391de35aa34d523c49355`；验证对象包含未提交的 package、service、CLI 修改，不是该提交的 exact-SHA CI。
- 独立 wheel SHA256：`071165f609b08baa40ccb42671438042e6c2166a551256f148e274a3f1cbfabb`。
- wheel、安装环境和合成项目均在本项目 ignored `.project-local/`，未使用用户真实设计工程。
- 使用 `--no-deps` 安装；只证明当前标准库服务切片，不证明完整 reconstruction 依赖可用。

## 已执行

1. 实际安装的 `venv/Scripts/design-lab.exe` 从非源码工作目录启动，显式传入拥有项目标记的测试根。
2. 创建中文项目名；第二个独立进程列出相同 ID、名称与时间，SQLite 实际位于合成项目的 `.project-local/task-runtime/service/state.db`。
3. 安装环境 `python -I -B` 的 `design_lab.__file__` 指向该环境 site-packages，而非源码 sys.path。
4. 五份 SQL 的源码、wheel 成员与安装副本逐字节一致；wheel console entry point 指向 `design_lab.cli:main`。
5. 源码 CLI 回归 4 项 PASS：跨进程持久化、只读查询不创建运行根、非法名称拒绝、无项目标记拒绝且不创建目标目录。

运行入口：`.project-local/task-artifacts/cli-qualification/verify_installed_cli.py`。脚本每次使用独立 UUID 新建合成记录，不覆盖既有记录；安装环境及脚本是本地证据，不随 Git 上传。

## 环境与限制

实际解释器为 `.venv/Scripts/python.exe`，Python 3.13.14，SQLite 3.53.1。全局指引提及的 `scripts/workflow/execution_preflight.py` 在本仓库不存在，调用失败已明确记录；改以该解释器直接导入 sqlite3 并输出版本，不把缺失工具报成产品测试失败。

首次终端显示中文发生编码替换；验证脚本追加原始 Python 字符串相等断言并以 ASCII JSON 输出，区分数据与展示编码。

尚未验收：HTTP API、任务/事件/取消、真实导入导出、UI、宿主调用、全依赖安装、升级/恢复、完整产品性能。此前全仓测试不覆盖这次新增切片；不得将本记录提升为服务任务或 M1 完成。
