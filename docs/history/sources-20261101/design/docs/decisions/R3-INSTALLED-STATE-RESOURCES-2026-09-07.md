# 安装布局状态 SQL 资源接入

状态：IMPLEMENTED_LOCAL / 定向 TESTED_LOCAL；未构建 wheel、未安装产品服务、未完成 R3-09。

`state_store`、`job_store`、`asset_store` 改用共同 `state_schema(name)` 定位五个固定 SQL。安装包读取 `design_lab/resources/state`；源码布局仍读取唯一编辑源 `design-lab/schemas/state`。不存在的安装资源明确失败，不从 CWD、用户目录或邻近项目借用资源。未复制第二份 SQL 编辑源，构建步骤负责将原件纳入发行包并核对 hash。

RED：真实复制的安装布局从非源码位置导入现有 store，原代码在读取 DDL 时 FileNotFoundError。GREEN：改用资源解析后，在无源码 schema 的安装布局中依次执行五个 SQL，SQLite 表创建成功。另覆盖未知/穿越资源名拒绝，以及安装资源缺失时不因 CWD 恰好是原仓库而假通过。

命令均使用 `.venv/Scripts/python.exe -B -m unittest discover -s design-lab/tests -p <module> -v/-q`，无新增依赖：

- `test_installed_state_resources.py`：安装布局与缺失/非法资源边界。
- `test_runtime_attempt_safety.py`：23 PASS。
- `test_runtime_asset_safety.py`：18 PASS。

测试资源、复制的包、SQLite 夹具仅在本项目 `.project-local/task-runtime/installed-state-resource-tests` 内；SQLite 迁移正例使用内存 DB。没有写安装目录、用户工程或全局环境。

检查时现有项目环境没有 setuptools/build/wheel；未盲目安装。下一步需要选择并锁定构建后端、加入真实 wheel 资源构建、处理显式项目根，再验证非仓库 CWD 的已安装 CLI/服务。当前改动只解决 SQL 定位前置，不把健康检查或安装布局替身作为完整产品验收。
