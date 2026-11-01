# R3 证据收尾、H3 完整性与 Photoshop 启动错误

状态：局部验证 PASS；仓库规范化和产品目标整体仍 PARTIAL。不是宿主设计验收、H3 推理成功或发布证书。

## 1. 本轮实际收尾

- 本轮开始 `scripts/generate_current_reports.py --check` 返回 DRIFT：`PROJECT_STATUS.json`、`PROJECT_STATUS.md`、`TASK_PROGRESS.json`、`current-report-index.json`。没有把旧状态表当当前完成统计。
- 新增测试入口证据与公开历史 overlay 证据已经追加到正式 ledger，旧 receipt 保留。重新生成 current 后 `--check` PASS。
- [文档修改后定向核验](../../.project-local/task-artifacts/test-entry/handoff-20260906T192318127345Z/results.json)：85 个真实测试、零跳过，Comfy policy 与许可门 PASS；链接存在性与旧测试源码哈希重新读回通过。
- 上轮完整套件是 756 项（755 PASS、1 skipped）、49 统一门通过。本轮没有重跑或重盖上轮完整测试时间；新增证据区分了早期完整测试与后续定向检查。
- [公开历史独立读回](../../.project-local/task-artifacts/history-public-git/verified-20260906T192404159811Z/results.json)：884 检查通过，实际读取 145 个 Git blob、3 个提交树；有效状态 289 可取回、4 占位、243 未解决。原 536/1450 与历史基线字节未改；`history_complete=false`。

## 2. H3：四文件全量字节校验已经完成

固定公开来源：[Comfy-Org/MiniMax-H3 revision 4cc1d817](https://huggingface.co/Comfy-Org/MiniMax-H3/tree/4cc1d817b6184899b41293954329f576cb5ae86b)。运行时从该固定 revision 的公开 API 取得 LFS SHA256 和长度；不以本地自算 hash 反向制造上游来源。

实际读取用户已登记模型库中的四个文件，共 **42,470,585,471 字节**；文件与全部祖先无 reparse/link，读取前后 size/mtime/inode 一致。没有下载、修改或复制这些权重。

| 组件 | 字节 | 全量 SHA256 与固定上游 |
|---|---:|---|
| diffusion INT8 | 20,970,379,616 | MATCH，`e889202c…` |
| Qwen3-VL text encoder NVFP4 AWQ | 15,687,142,551 | MATCH，`35a88d51…` |
| video VAE FP16 | 5,207,808,496 | MATCH，`7c1f1314…` |
| audio VAE FP32 | 605,254,808 | MATCH，`8e505d95…` |

[完整哈希、时间与输入记录](../../.project-local/task-artifacts/h3-qualification/20260906T193014699719Z/results.json)，[固定上游元数据](../../.project-local/task-artifacts/h3-qualification/20260906T193014699719Z/upstream-metadata.json)。此结论只覆盖这四个组件，不代表任意工作流所需的全部节点、嵌入或扩展都完整。

## 3. 现有 ComfyUI 环境实测

[真实内嵌解释器结果](../../.project-local/task-artifacts/h3-qualification/20260906T193014699719Z/embedded-runtime.json)：

- 使用已安装 `python_embeded/python.exe -I -B`，不是主仓库 venv。Python 3.13.14；Torch 2.13.0+cu130；Torch CUDA 13.0。
- Torch 导入 exit 0、stderr 空；CUDA available=true；实际设备 NVIDIA GeForce RTX 5060，显存 8,546,484,224 字节，compute capability 12.0。
- ComfyUI 公开版本源 `comfyui_version.py` 为 0.33.1；这是版本源读取，不是服务启动或工作流执行。
- 子进程 temp/cache/HF/Torch 路径限定项目 `.project-local/`，离线标志开启；没有安装依赖、改变共享环境、启动 ComfyUI 服务或加载 H3。

不能从权重总量与显存简单比较推断“能运行”或“永远不能运行”。还缺实际节点/算子支持、调度/offload 策略、加载与推理峰值及输出验证。

## 4. 许可与人工审计边界

[固定 MiniMaxAI revision 的 LICENSE 来源](https://huggingface.co/MiniMaxAI/MiniMax-H3/raw/42ed227ee7df40d41602854ae760620d6eb651fe/LICENSE)已读取并保存为 inert source：[来源与哈希记录](../../.project-local/task-artifacts/h3-qualification/license-20260906T193212972936Z/results.json)。17604 字节，SHA256 `59b99642b95ea21630e311198ddbfffbfe05aadba0c2f5d884cbdf4efcc90f44`。

采集许可不等于批准用途或签署 Human Gate。实际适用地区未确认；不能从时区推断，也不能把个人测试条件写成永久商用阻塞。模型 profile/trust 未改变、默认未启用。`LOCAL_INFERENCE_VERIFIED` 仍 NOT_EXECUTED。

## 5. Photoshop 启动：记录错误，不归咎于模型或未安装

Computer Use 返回已安装应用 `Adobe Photoshop 2025`，程序文件也存在。开始时只有 Illustrator 任务窗口，没有返回 Photoshop 窗口。

两次 `sky.launch_app` 均返回：`accessibility window-opened handler did not become ready`。第一次使用已登记 exe；只读复查后重置 JS 会话，第二次使用 `list_apps` 返回的准确 app id。后续未观察到 Photoshop 进程，未进入文档操作。

结论仅为 **AUTOMATION_LAUNCH_FAILURE**，Photoshop 图层/保存/重开测试 **NOT_EXECUTED**。没有再次安装、修改系统权限、安全设置或用旧窗口坐标重试。不得宣称 Photoshop 产品崩溃、未安装或图层功能测试失败。精确错误亦保存在上面的来源与哈希记录。

本轮其他定位错误：通用 `scripts/workflow/execution_preflight.py` 在本仓不存在，改为确切主环境依赖导入检查且通过；误查 `comfy_version.py` 后用限定公开源码列表找到 `comfyui_version.py`。这些是入口/文件定位问题，不是产品回归。

## 6. 下一步与不变范围

按 R3 依赖接续实际入口和 Adobe/模型资格，继而服务、工作台与参考图复刻；未完成项不因测试数量或本报告升级。H3 专项不阻塞首个 AI/PS 可用版本；知识迁移延后。

四外置根仍以 `.project/paths.json` 为准。所有新增证据在 ignored 项目根，换机不存在必须显示 MISSING。没有提交、上传、PR、发布、读取 E 盘或私人 Agent 状态；人工审计和发布门保持待验收。
