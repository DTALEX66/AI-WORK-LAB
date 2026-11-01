# OCR 准备实测与原生缓存边界阻塞

状态：**PARTIAL / OCR 推理 NOT_EXECUTED**。官方模型完整性、短路径安装和 pip check 已通过；实际导入因默认仓外缓存写入被保护器中止。独立 34 项核验通过只证明本报告中的准备与失败证据，不证明 OCR 成功。

## 已完成的实际工作

1. 只读检查已登记模型库顶层及项目 `.project-local/cache/models/huggingface`，未发现本次可复用的 OCR 权重。旧报告指向用户目录且称只有 refs 指针；本轮没有读取该用户缓存，不作“全机未安装”的结论。
2. RapidOCR 3.9.2 固定 GitHub 提交 `095232a4c94f7f0e6600ba5bba1177010ad696d4` 的发布清单可取回，但所列 ModelScope 检测模型 URL 返回 403。未尝试凭据、镜像绕行或重试同一下载；该 GitHub release 的附件列表为空。改查 PaddlePaddle 官方原生同代模型，而非降低为其他 OCR 代际或尺寸。
3. 官方 PP-OCRv6 medium det/rec 的八份文件（含各自 README/结构/参数/预处理配置），共 **139,157,714 字节**已在项目内下载并核验。LFS 参数核 SHA256；其他文件核固定 revision 的 Git blob SHA1，再绑定本地 SHA256。模型元数据声明 Apache-2.0，不自动签署产品 trust/rights。

| 模型 | 固定官方 revision | 参数字节与 SHA256 |
|---|---|---|
| [PP-OCRv6_medium_det](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_det/tree/8e0f56fb2ef86b461d99cfc7ac5c137738985f61) | `8e0f56fb2ef86b461d99cfc7ac5c137738985f61` | 61,960,476；`85218d2e3d98f5a21c58b4220627be923a97aee5db3cc71f39536ab31ac53960` |
| [PP-OCRv6_medium_rec](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec/tree/e5a92bcbc5cc1b494628e458d267778f0704fd7c) | `e5a92bcbc5cc1b494628e458d267778f0704fd7c` | 76,465,087；`1b01c79a914587933f615569e75de54f2e638ebb5d3f3b3c1b38c24ede8c7319` |

本次原生依赖：Python 3.13.14、PaddlePaddle 3.3.1 Windows CPU、PaddleOCR 3.7.0、PaddleX 3.7.2。只装基础 OCR 依赖，未启用 all/文档生成/云推理 extras，未修改主 venv、ASR 或 ComfyUI 环境。

## 错误 1：260 字符安装路径，已验证恢复

长路径环境安装 ModelScope 依赖时返回 Errno 2，失败成员绝对路径恰为 260 字符。旧环境和日志保留，不清理或覆盖。

改为本项目短根 `.project-local/task-runtime/o6-01/v/`，所有包名/版本来自原 install-report 固定集合，重新安装复用项目缓存。独立比对两次 resolved 版本与 distribution SHA256 完全相同；此前失败成员现在为 **215 字符**，存在且 hash 已绑定。安装耗时 28.233 秒，pip check exit 0；未改注册表、系统长路径设置、ACL 或 Git 全局配置。这是已验证的本次路径恢复，不代表产品安装器已支持所有深度。

## 错误 2：Paddle 导入仓外缓存，仍阻塞

专用脚本先生成英文、中文、电商文字排版、反色和无文字几何五份合成图片，再导入 Paddle。已经设置项目内 TEMP/TMP、HF_HOME、PADDLE_HOME、PADDLE_PDX_CACHE_HOME、MODELSCOPE_CACHE；离线且不给模型参考答案。

实际 `import paddle` 经过 `paddle.text.datasets → paddle.dataset.common`，在 `must_mkdirs(DATA_HOME)` 尝试创建 `C:/Users/ALEX/.cache/paddle/dataset`，被 Python audit guard 拒绝。该地址仅来自失败事件，未枚举或读取其内容。

当前安装源码 `paddle/dataset/common.py` 第 46/56/62 行将数据集根硬编码为用户 HOME 下的 `.cache/paddle/dataset`，导入即调用 mkdir；该模块不读取 `PADDLE_HOME`。不能据另一个 PaddleX 缓存支持环境变量，就推导所有 Paddle 缓存均已归入项目。

**未加载 det/rec 模型、未产生预测框或识别结果。** 不重复启动，不关闭保护，不改厂商已安装源码、不重映射用户 HOME/USERPROFILE、不创建用户缓存目录求绿。下一步原生路线需要明确可审查的隔离方案，或取得官方可校验 ONNX 发布再走不触发原生 Paddle 导入的路线；当前没有验证其中任何一个。

另外 guard 将 Windows `\\.\NUL` 丢弃设备当成文件写入拒绝，属于诊断器过严，须在后续新版本中以精确设备语义处理；不能把这个误报称为用户数据外溢。它与后续真实用户目录 mkdir 是两件事。ccache 未发现警告只涉及构建缓存，不是 OCR 模型缺失。

## 审计材料与接续断点

首次入账误把两份大权重直接列入报告读取文件，触发生成器 32 MiB 单文件上限。已仅移除这两个直接读取引用，保留模型原文件及 preparation/独立核验中的完整路径、大小、hash；没有放大安全限额或删除权重。报告不会自动重哈希这些大权重，需上述专用 verifier 实测；生成器随后 generate/check 均通过。

本轮数据均在项目 `.project-local/`；软件模型仍是候选，未改 profile/trust、正式生产接口或全局配置。未写共享模型库或工具链、未读 E 盘/凭据、未提交或上传。原始失败、部分环境和模型保留；其删除需另行明确范围。

- [RapidOCR 下载失败原件](../../.project-local/task-artifacts/ocr-qualification/20260906T201809209621Z/preparation.json)
- [官方源核验与长路径安装失败](../../.project-local/task-artifacts/ocr-qualification/paddle-20260906T202022263722Z/preparation.json)
- [短路径环境恢复](../../.project-local/task-artifacts/ocr-qualification/paddle-20260906T202022263722Z/short-env-20260906T202539513167Z/preparation.json)
- [导入实际失败结果](../../.project-local/task-artifacts/ocr-qualification/paddle-20260906T202022263722Z/live-20260906T202626725459Z/results.json)
- [具体调用栈](../../.project-local/task-artifacts/ocr-qualification/paddle-20260906T202022263722Z/live-20260906T202626725459Z/error.json)
- [预先定义的图片与验收协议](../../.project-local/task-artifacts/ocr-qualification/paddle-20260906T202022263722Z/live-20260906T202626725459Z/protocol.json)
- [独立 34 项读回](../../.project-local/task-artifacts/ocr-qualification/paddle-20260906T202022263722Z/verified-20260906T202906121417Z.json)

复核命令：`.venv/Scripts/python.exe -I -B .project-local/task-artifacts/ocr-qualification/verify_preparation.py`。它不运行 OCR，也不重装；生成独立新结果，原日志不改。

R3-02 的实际入口隔离因此仍有缺口；R3-08 保留 ASR 受控实测并继续 PARTIAL，不被这次安装通过提升。依赖阻塞只限当前 OCR 原生候选路线，不等于整个目标不可推进。知识迁移延后，H3、Adobe、工作台及最终人审分别待闭环。
