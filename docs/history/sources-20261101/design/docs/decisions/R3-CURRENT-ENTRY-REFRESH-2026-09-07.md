# 当前入口规范化：证据接续修正与统一门新失败

本轮状态：**PARTIAL**。只修正活跃接续文档，未修改产品代码或运行新的宿主/模型任务。完整统一门为 **47 PASS / 2 FAIL**，不是全绿。

## 已修正

- [本机环境](../LOCAL_ENVIRONMENT.md)：保留四个外置根，将软件安装登记、已有运行观察、剩余产品资格分开；ASR 不再误写“真实转写待完成”，H3 不再漏掉四组件完整性结果，新增 OCR 隔离失败入口。
- [GPT 接续包](../taskpacks/DESIGN-LAB-GPT-REMAINING-2026-09-06.md)：正式状态直接引用生成投影；ASR 早期 HTTPS/缺包断点及 H3 早期调研保留为明确历史，新增当前接续。CI 已有本地修改不重复派工，仍待干净 checkout 与 exact-SHA CI。
- 未改 DP V1/V2、历史任务定义和审计原件；知识迁移继续延后。文档刷新不是运行证据刷新。

## 本轮实际核验

运行根：`.project-local/task-artifacts/normalization-20260907/20260906T205320957684Z/`。

使用现有 `.venv/Scripts/python.exe -B .project-local/task-artifacts/normalization-20260907/verify.py --post-full`，新建独占运行根，不覆盖旧测试。进程终态 exit 1，所有子命令与时间在[原始结果](../../.project-local/task-artifacts/normalization-20260907/20260906T205320957684Z/results.json)。

| 检查 | 结果 | 范围 |
|---|---|---|
| test_project_paths | 16 PASS | 既有路径合同回归，1.625 秒命令耗时 |
| test_current_reporting | 24 PASS | 既有报告合同回归，0.844 秒命令耗时 |
| unified | 47 PASS / 2 FAIL | 实际完整 49 道门，80.399 秒；下述同一根因 |
| license / doctor --paths | PASS / PATHS_RESOLVED | 许可覆盖检查及项目根解析，不是模型许可审批或全入口实测 |
| 文档引用证据 | 6 个 receipt 的 37 个 subject 引用、150 个 artifact 引用 hash MATCH | 现存证据读回，非重新推理；引用数可包含重复文件 |
| 相对 Markdown 链接 | 25 个目标存在 | 从各文档所在目录解析；外部 URL 未重新联网核验 |

[证据和文档链接读回](../../.project-local/task-artifacts/normalization-20260907/20260906T205320957684Z/entry-document-readback.json)。验证脚本所绑定来源在本次命令前后相同；未重跑完整 Python 套件，旧 756 项结果仍属于旧运行。

## 新复现：视觉质量校验误扫依赖环境

`design-lab/scripts/verify_visual_quality_v21.py` 第 55 行使用 `ROOT.rglob('*.json')`，对整个项目树每个 JSON 都尝试 `json.loads`，没有先排除 `.project-local`、依赖或私有状态。

本次误读 `.project-local/task-runtime/ocr-qualification/.../venv/` 和 `.project-local/task-runtime/o6-01/v/` 内 Paddle CINN tile_config 文件；18 条 `Extra data: line 2 column 1` 来自这些第三方调优数据。它们不是 DESIGN-LAB 视觉质量 JSON 合同，不能为了校验器将其改写或删除。

统一门中直接执行该脚本失败；Open Design adapter verifier 又将该脚本作为 secondary verifier，因此同一根因传播为第二道失败。不是 Open Design 软件启动失败，也不是下载的模型权重损坏。完整信息见[统一门日志](../../.project-local/task-artifacts/normalization-20260907/20260906T205320957684Z/unified.log)。

已提出小范围设计：在遍历前排除项目运行根、依赖和私有状态，保留项目源码 JSON 的真实语法失败；补“运行夹具不被遍历、坏源码仍失败、链接不穿越”等回归。按 brainstorming 技能等待设计确认，产品脚本尚未修改。确认并修复前不再次运行已知会广泛扫描的该脚本/统一门，不清理依赖环境求绿。

## 正式状态处理

追加新鲜、限定于入口/路径回归的证据，不回填旧 receipt 的 hash 或时间。旧规范化 receipt 因活跃文档改变可显示 STALE；新 receipt 只承接这次确实重验的范围。另追加统一门 FAIL 证据，R3-04 unit 降为 PARTIAL，避免继续显示全部本地门通过。

R3-02 多入口隔离、OCR 导入边界、Adobe 产品桥、服务/UI/M1、H3 推理、人审与发布仍未闭环。未提交、推送、发布、修改全局设置、清理或迁移数据；本次新产物仅在项目内。
