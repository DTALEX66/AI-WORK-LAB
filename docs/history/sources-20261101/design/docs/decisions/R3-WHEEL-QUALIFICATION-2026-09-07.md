# 真实 wheel 构建与安装资源核验

状态：构建 PASS、隔离安装 PASS、安装后 SQL 资源/导入 PASS；产品服务、CLI 和完整依赖资格仍未完成。

## 构建选择和边界

依据 [Hatch 官方构建配置](https://hatch.pypa.io/latest/config/build/)，采用固定 `hatchling==1.27.0`、wheel `packages=["src/design_lab"]` 和 `force-include` 将唯一 SQL 源映射到 `design_lab/resources/state`。sdist 显式限于 package 源码、SQL 和 pyproject，不扫描整个运行树。

`pyproject.toml` 现在启用 package；`uv lock` 实际执行，现有锁文件仅将本项目 source 从 virtual 改为 editable，其他依赖版本未变化。

所有构建缓存与安装环境在本仓 `.project-local`；设置 `UV_CACHE_DIR` 为 `.project-local/task-runtime/wheel-build/uv-cache`，`UV_PYTHON_DOWNLOADS=never`。使用既有 uv 和 Python 3.13.14，没有安装全局 Python 或修改全局配置。

## 实际执行

1. `uv build --wheel --python .venv/Scripts/python.exe --out-dir .project-local/task-artifacts/wheel-qualification/dist`：成功。
2. `uv venv --python .venv/Scripts/python.exe .project-local/task-runtime/wheel-qualification/venv`：成功。
3. `uv pip install --python .project-local/task-runtime/wheel-qualification/venv/Scripts/python.exe --no-deps .project-local/task-artifacts/wheel-qualification/dist/design_lab-0.1.0a0-py3-none-any.whl`：真实安装成功。
4. 从 `.project-local/task-runtime/wheel-qualification` 非仓库 CWD，以已安装环境 Python `-I -B` 执行验证脚本：成功，导入路径实际位于该环境 site-packages，不是仓库 src。

wheel SHA256：`4ac1487154eafb4694fdb47928471ef1d36ecb944ca0b92af405305e0efa330c`；33 个 ZIP entries。五个 SQL 的源码、wheel 和安装资源字节全部相同；安装资源在内存 SQLite 中执行五个 schema/迁移后，operation、project、asset_version 等表实际存在。

构建工具警告缓存位于源码树中、可能被纳入发行物。实际 ZIP 清单已核验：只包含 design_lab 与 dist-info，不含 `.project-local`、`.hermes`、依赖环境、模型或缓存；没有靠忽略警告宣称安全。

验证脚本和 wheel 都保留 `.project-local/task-artifacts/wheel-qualification/`，不上传二进制发布件。脚本 `verify_installed.py` 可从非仓库 CWD 重新核验当前 wheel。

## 不能越级的结论

本次 `--no-deps` 只证明纯标准库 runtime 模块及 SQL 资源；没有宣称 OCR/图像分析等完整依赖已安装。包尚无产品 CLI/HTTP 服务入口；运行数据库路径仍需显式项目根接入。资源验证使用内存 DB，不是已安装服务写入用户工程的证据。sdist 到 wheel 的往返构建、安装/升级/恢复、exact-SHA CI 和完整服务流程还需接续。
