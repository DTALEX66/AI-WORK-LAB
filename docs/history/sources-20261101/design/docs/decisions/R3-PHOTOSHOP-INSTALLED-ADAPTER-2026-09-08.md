# Photoshop 可安装原生适配器交接

## 已推进到哪里

在 `1b1da34bad1b58d02d41925266b7d20614569846` 上继续实现。该基线的 GitHub Actions `34151256703` 已读回 success；不是本轮新提交的 CI。当前新增 `src/design_lab/adapters/photoshop_com.py` 并将固定 JSX 纳入 wheel，**隔离安装包已经直接控制真实 Photoshop 26.7.0，生成 PSD/PNG、关闭重开/结构读回、封存输入输出 hash，文档数 0→0**。

这是原生 COM/ExtendScript 内部 adapter，不是 UXP 资格、HTTP 任意脚本入口或整套工作台闭环。R3 仍是任务状态权威，知识迁移延后。

## 产品入口与边界

```python
from design_lab.adapters.photoshop_com import execute
receipt = execute(job, project_root=project_root, approved_root=run_root)
```

- Python 预检：封闭根字段、JSON 冻结、完整 job hash、画布/输入图像预算、项目解析器与 run 路径、现有输出拒绝、真实 PNG/JPEG 校验。
- 固定软件 ProgID 和桥资源；脚本只走 stdin；不读取凭据/用户配置、不改 execution policy、不做 GUI 操作。
- 宿主建文档前验证图层/字体/蒙版等合同；执行后验证 job hash 回执、原有文档 ID 顺序及数量、恢复此前活动文档；Python 检查输入不变、PSD 头及尺寸、PNG 及尺寸、输出 hash。
- 预检错误不声称发生副作用；进入 COM 后错误/超时均为 `outcome_unknown=True`，不自动重试、不终止 Adobe、不删除部分工程。
- 调用方仍须持有单写租约，处理 rights、operation/attempt、取消对账和原子资产发布。当前 API 没有这些职责，也尚未暴露 patch 或接通工作台按钮。
- 打开输入图片若已经存在于 Photoshop（包括有未保存修改），桥在创建新工程前拒绝，避免 `open → finally close` 关闭用户已打开的输入。

## 安装后的真实运行

Wheel：`.project-local/task-artifacts/photoshop-com-wheel/design_lab-0.1.0a0-py3-none-any.whl`

- SHA256 `0e81695c199ad3ffcdac7e7bc385546f0b9377c6f3b2749cfea18c4c658ae62b`。
- 48 个归档项；Photoshop 桥与仓库逐字节一致；无 `.project-local` / `__pycache__` 项。uv 的“cache 在 source 内”警告已按实际归档核验。
- 仅在项目内资格环境 reinstall，本机系统/用户级 Python 未修改、未发布 release。

命令：

```powershell
.venv/Scripts/python.exe -B design-lab/tests/host_fixtures/prepare_photoshop_native.py --installed-python .project-local/task-runtime/workbench-installed/Scripts/python.exe
```

子进程使用 `python -I -B`，cwd 为新运行目录，实际 module 位于 `.project-local/task-runtime/workbench-installed/Lib/site-packages/design_lab/adapters/photoshop_com.py`，没有源码路径注入。

最终运行目录 `.project-local/task-artifacts/photoshop-native-20260908/run-d7f622de47cd4365971bdf9e07fdf7b9`；UTC `2026-09-07T18:26:27.942692+00:00` 记录。Windows 11 build 26100；宿主 26.7.0。

| 绑定对象 | SHA256 |
|---|---|
| adapter 源码 | `653f2e01e679b04a5c77e11065cdc569855f3265bb67ee9983872bb8ea4138f8` |
| 桥源码（增加打开输入保护） | `1bab069422dcf520e8527d73c1f884b615720fc80fc9d3b058f5999d6fcf3c30` |
| 完整 job | `6ba4e1b88f01a4d5878873d6132cfe3c967272292705a3075c348e6a33a3030b` |
| baseline.psd | `82476ede7453f7afead38cde48669fd69f1d12e427c2526c05ae871ad463a361` |
| baseline.png | `42171edec57d309c2dc9b0cdd7f8c0a19fb750ebe1652a5dd637812e9f765265` |

实测发生在基线 SHA + 本轮未提交候选源码，以上 hash 才是精确候选绑定，不能声称基线提交已包含新代码。产物和 `installed-readback.json` 保留 ignored 本地，换机不能伪造。

## 负向实机与回归

- 适配器缺失时先观察 6 项 RED，实现后通过；路径越界、覆盖、错误类型/尺寸、非图像、超时、错误回执、产物缺失、输入变化均有真实文件测试（仅 COM 边界 double）。
- 打开输入保护先观察缺失函数 RED，再实现；包含 `saved=false` 的打开文档，不以 saved 标志判断是否有文件身份。
- 安装包负向实机：专用 32×32 RGBA PNG，新建 UUID 目录；打开并改层名，使其有未保存修改。调用产品 adapter 被拒，无 output.psd/output.png；读回仍是 `1|269|false|QUALIFICATION_UNSAVED`，原输入 hash 未变。随后仅关闭 ID 269 的自建测试文档，文档数回到 0。没有关闭用户文档。
- 负向记录 `.project-local/task-artifacts/photoshop-open-input-20260908/run-5548e498c2d0493f8dd3599bb7f7e75d/result.json`；UTC `18:27:53.817196+00:00`。输入 SHA `ba83c6adb54d8b3245a21f8ef9b5cb23c5db416b272872d1d1c563403e7f3b74`。该轮使用一次性固定测试命令，非后台守护进程。
- Photoshop 定向组 10 项 PASS；隔离安装包 HTTP 回归 17 项 PASS、7.892 秒。单测 PSD 头 fixture 不冒充真实原生工程，实机证据来自上述单独运行。
- 统一检查会话 78276 终态退出 0，`VERIFY_DESIGN_LAB=OK total=49 failed=0`。报告生成和 `--check` PASS。统一检查中的历史 Comfy E3 文案不代表本轮模型推理；新提交全量单测及 CI 仍需精确 SHA 另验。

## 下一步，不重新缩小目标

优先将 AI/PS 内部 adapter 接入持久化任务执行器、host lease、取消/失败对账和资产发布，再接工作台。将 RIR builder 与引用拆解接入已安装服务，补复杂参考 5–10 张、两次局部修改/恢复、人审、rights、production。前轮 JSX 两次修改证据保留于 `R3-PHOTOSHOP-NATIVE-ROUNDTRIP-2026-09-08.md`，本轮安装 API 仅验证新建/重开，不宣称安装 API 已支持 patch。Comfy/H3 小说分镜 15 秒视频仍独立待做；当前模型许可/资源门不放宽。

接线参考现有 `src/design_lab/image_assets.py`、`runtime/job_store.py`、`runtime/asset_store.py`，不要建立第二套任务数据库。特别注意：宿主 COM 超时不证明脚本已停止，不能只复制 import 的 `finally: release_writer` 或等待 60 秒租约过期后启动下一宿主任务；需要持久化未决执行阻挡，并在真实对账确认后才释放宿主写权限。
