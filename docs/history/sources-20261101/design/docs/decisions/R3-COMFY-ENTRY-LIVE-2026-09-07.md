# ComfyUI 真实入口、路径与协议审计

结论：本切片受控运行 **PASS**；R3-02 / R3-16 整项 **PARTIAL**。本次是无模型像素夹具，不是 AI 设计生成、H3 本地推理或生产适配器完成。

## 实际运行

2026-09-07，复用已登记 ComfyUI portable，版本 0.33.1、内嵌 Python 3.13.14。没有重装、修改共享安装或连接用户现有实例。

用户当前授权自动化实测；本次由独立诊断控制器显式启动专用进程，不修改生产适配器“用户手动启动后连接”的默认策略。两轮各使用空闲 loopback 端口，均在结束后停止自己创建的进程，未停止其他软件或 ComfyUI 实例。

| 轮次 | 工作目录 | 实际子进程 PID | 服务端口 | 服务就绪耗时 |
|---|---|---:|---:|---:|
| 1 | 仓库根 | 30784 | 59489 | 9.604 秒 |
| 2 | 本项目 ignored 的 foreign-cwd | 22412 | 59515 | 6.605 秒 |

第二轮为同一专用 base/output/user/数据库目录的重新启动；不是两台机器验收，也不是标准化冷/热性能基准。

## 已执行场景

- 真正请求 `/system_stats`，取得运行版本及 GPU 信息。
- 建立 WebSocket，校验服务返回的 `sid` 与 `client_id`；通过 REST `/prompt` 提交固定 `EmptyImage → SaveImage` 工作流，按真实 `prompt_id` 收到 `execution_success` 并读回 `/history/{prompt_id}`。
- 两轮各实际产生一个 64×64 RGB PNG；所有像素均为 `(18,52,86)`，独立读回逐字节验证，文件 SHA256 均为 `b0e49e6fdcd49c416d72513b0af959579be0788ccaed03bd99fab372e7134b2d`。
- 同图再次提交，获得不同的 prompt ID；服务明确发出 `execution_cached`、节点 1/2 均命中，未新增 PNG。标为 **CACHE_REUSE_NOT_NEW_GENERATION**，不把服务 success 包装成新生成。
- 关闭 WebSocket、重连相同 client ID，再按任务 ID 读回历史。
- 提交确定不存在的测试节点，收到 HTTP 400 且没有成功任务 ID；测试结束队列为空。
- 重启后原 prompt ID 的 `/history` 返回空对象，已留原始响应。产物字节仍在，但历史不在：**ComfyUI 内存历史不能代替 DESIGN-LAB 自己的持久任务/回执**。这不是“恢复已完成”的证据。

原运行 44 项检查通过；独立读回 129 项检查通过。完整材料在：

- [实际运行结果](../../.project-local/task-artifacts/comfy-normalization/20260906T194131462525Z/results.json)
- [独立核验结果](../../.project-local/task-artifacts/comfy-normalization/20260906T194131462525Z/independent-20260906T194359544174Z.json)
- [首轮启动与路径配置](../../.project-local/task-artifacts/comfy-normalization/20260906T194131462525Z/round-1-launch.json)
- [首轮原始服务日志](../../.project-local/task-artifacts/comfy-normalization/20260906T194131462525Z/round-1-server.log)
- [任务 ID、WS 事件及历史](../../.project-local/task-artifacts/comfy-normalization/20260906T194131462525Z/round-1-baseline.json)
- [缓存事件与历史](../../.project-local/task-artifacts/comfy-normalization/20260906T194131462525Z/round-1-repeat.json)
- [重启后的原任务历史](../../.project-local/task-artifacts/comfy-normalization/20260906T194131462525Z/prior-history-after-restart.json)

## 路径与观测边界

- 显式设置 base/input/output/temp/user 和 SQLite 数据库到本项目独占 run 根。临时目录实际为 `--temp-directory` 下的 `temp` 子目录；没有误用共享默认目录。
- 用已安装前端静态目录，不下载前端；Manager 未启用，所有自定义节点与外部 API 节点关闭，asset seeder 未启用。HF/Torch/CUDA/Triton/Numba/Matplotlib 缓存均指定在项目 run 根。
- 已安装 ComfyUI `main.py`、server、nodes、folder_paths、cli_args、extra model paths、版本源的前后 SHA 一致。公开 extra model paths 只指向用户已授权的 D 盘模型库；未读取其权重。
- 入口通过 `runpy` 在 Python audit observer 下执行，没有改写安装源码。记录实际 PID、父 PID 与 CWD；两轮共 **41 条 Python 文件系统修改事件**均限于专用项目根，零拒绝事件；独立检查两端口已不再监听。
- 这不是原生 DLL、SQLite 底层或全操作系统文件追踪；不能从 41 条事件推导“所有软件零外溢”。其他 Agent、Adobe scratch、产品 UI/服务仍各自待验。
- 为结束独占诊断，队列排空后对自己持有的 `Popen` 进程 terminate，终态 exit 1 是该停止方式的结果，**不算优雅退出或故障恢复通过**。没有删除旧数据库、作品或用户资料；测试数据保留供审计。

## 警告与剩余工作

- Pillow 输出 `getdata` 弃用警告；像素检查实际通过。独立验证使用 `tobytes`，不重写已冻结运行脚本或旧证据。
- Triton 不可用且禁用、HIP/ROCm 不可用、OpenGL_accelerate 缺失。当前所选两个原生节点实际可执行；不外推其他模型/算子可用，也不为消除提示安装无关依赖。
- 运行中取消、队列取消竞态、GPU 模型生成、完整图拓扑指纹、项目资产服务回收及重启对账尚未通过本次验收。现有 `src/design_lab/generators/comfy_task.py` 仍是结构层，本探针不是替代产品实现。
- 下一步应把本次确认的真实 API/缓存/重启语义接入项目 Operation/Attempt、资产版本和持久回执；H3 继续单独验证许可适用、加载、资源峰值和真正音视频输出。

本仓 SHA 仍 `c4dccd58331bc4561eb89265283d924b7630d113`，证据绑定工作树文件哈希；未提交、上传、创建 PR、发布或代签 Human Gate。知识迁移延后。
