# OCR ONNX 受控推理交接

状态：CONTROLLED_OCR_PASS；仅合成样例 CPU 检测+识别，不是复杂设计集、人审、生产 provider 或发布通过。

## 新证据及旧错误

原 Paddle 路线触发用户目录缓存边界，仍保留为失败记录；没有修改第三方源码、重定向 HOME、降低保护或伪造成功。新路线使用固定 revision 的 PP-OCRv6 medium ONNX 模型与项目内隔离 RapidOCR/ONNX Runtime 环境，不依赖 Paddle import。

首次 ONNX 模型已加载，但独立调用 TextRecognizer 缺少 wrapper 平常注入的 `Rec.font_path`，产生 `ConfigAttributeError`。失败结果保留在 `live-20260907T194011555290Z/results.json`。修正调用方，显式使用已有 Windows 字体 `C:/Windows/Fonts/msyh.ttc`；不下载或分发该字体。随后一次完整运行成功。

## 已核验结果

模型证据根：`.project-local/task-artifacts/ocr-qualification/onnx-20260907T193520352697Z`。

成功结果：该根下 `live-20260907T194047051121Z/results.json`；SHA256 `a7b581bd7f060b707ac743c855d5179b7cd28af69162c6268884f87e5406f565`，进程会话 95640 退出 0。

| 样例 | 文字行 | 检测+识别秒数 | 结果 |
|---|---:|---:|---|
| english | 3 | 1.299 | PASS |
| chinese | 3 | 13.169 | PASS |
| commerce | 4 | 13.552 | PASS |
| inverted | 3 | 13.415 | PASS |
| blank | 0 | 12.696 | PASS，无额外文字 |

13 行的归一化 CER 全为 0；bbox IoU 最低 0.6867507886435331。预声明门为 IoU >= 0.35、归一化 CER <= 0.1、不得额外识别文字、数量一致。归一化会忽略部分标点及空白，不等于所有原始字符逐字节相同。预期答案只用于推理后评分，没有传入模型。模型加载耗时 0.257 秒；上述少量受控样例不是生产性能基准。

本轮额外独立读回全部 8 个模型文件，SHA256 与结果记录一致；5 个样例通过，13 个识别对象，拒绝事件为 0。Python audit hook 拒绝网络、子进程、受保护目录读取及运行目录外写入；这是 Python 事件层边界，不是操作系统级原生 DLL I/O 审计。ONNX telemetry 已关闭。

## 固定输入与复现

- 检测模型：`PaddlePaddle/PP-OCRv6_medium_det_onnx` revision `61323801669c338b7891481ec7bac61ce31b576a`，ONNX SHA256 `eb13b44b25bb36f89528b68720af8a61d9cf381176107f465db1757b65d086e1`。
- 识别模型：`PaddlePaddle/PP-OCRv6_medium_rec_onnx` revision `50c7eacafc52fa7bcf4194e8cd08e46f8558504b`，ONNX SHA256 `9c09abf0957f7968c7586464b7397b84ad2387a0497a351af40e9acc71b673ba`。
- 下载记录 `preparation.json` 的 WEIGHTS_COMPLETE_NOT_LOADED 是冻结准备时状态，不回写成推理通过；后续推理由独立 results 证明。
- 模型元数据记录 Apache-2.0；不是项目 rights 审批或默认启用凭证。
- 环境：`.project-local/task-runtime/ocr-onnx-01/v/Scripts/python.exe`，Python 3.13.14、rapidocr 3.9.2、onnxruntime 1.29.0、numpy 2.5.3、opencv-python 5.0.0.93。
- 原始执行脚本 `.project-local/task-artifacts/ocr-qualification/onnx_live.py` SHA256 `747844c1cf6cdce6d4bbd828598f2bfe49f1ec8e3523f0ee8732eff027467d1b`。
- 固定 fixture protocol：`.project-local/task-artifacts/ocr-qualification/paddle-20260906T202022263722Z/live-20260906T202626725459Z/protocol.json`，SHA256 `2f8724aaca4ced708208bd757d97682bf98b7886833436f6df205ad28db30b98`。

保留了对应仓库夹具 `design-lab/tests/host_fixtures/qualify_ocr_onnx.py`。从仓库根执行：

```powershell
.project-local/task-runtime/ocr-onnx-01/v/Scripts/python.exe -I -B design-lab/tests/host_fixtures/qualify_ocr_onnx.py
```

每次创建新时间戳目录，不覆盖旧结果。模型、环境、fixture PNG/protocol 都是本地 ignored 输入；换机器若缺失应报告 MISSING，不重建假记录。脚本是本机固定资格夹具，不是通用安装器或产品 OCR API。

复测时仓库夹具与原运行脚本 SHA256 完全一致。再次真实执行该仓库路径，会话 45039 退出 0，5 类全部通过且拒绝事件为空。新结果 `live-20260907T194844712383Z/results.json` SHA256 `c015ad6dc300122413cc76944d5d5d9510ce1c0556a6b10e6370e120f0fc298a`。这是第二次受控复现，不是两份不同复杂参考案例。后续综合检查发现归档脚本缺失 SPDX 头，仓库版本仅补 MIT SPDX 注释，hash 随之变化；旧运行仍绑定上面历史脚本 hash，不重写旧证据。

## 分支交付观察

安装版 RIR 实现已提交为 `81a14eecfc6be8fe9b679f91d3249af736641f3f`，其 reconstruction 回归 277 项通过。随后 `git push origin codex/r3-runtime-correctness` 被执行环境拒绝：`approval required by policy, but AskForApproval is set to Never`。用户授权已存在，但本轮没有绕过运行环境策略。

拒绝后直接 `git ls-remote` 读回开发分支仍为 `ed8d45ab2857b312f6056c43f7bb5e19dd9b65eb`，main 为 `c4dccd58331bc4561eb89265283d924b7630d113`。因此本批为本地交付，不能称双端一致或新 SHA CI 已通过。策略恢复后仅推送现有开发分支并读取 exact SHA / CI；不强推、不推 main、不新建 release。

## 下一步及不可抵扣项

将真实 OCR 输出接入可纠正的对象计划，补复杂参考、区域/对象分离、字体选择与置信度，再经原生 AI/PSD 执行两次局部修改。不得把本次合成电商文本样例计入用户要求的知名设计网站参考复刻集。未启用全局 provider 或 H3，未将模型/输入/运行原件上传；知识迁移继续延后。
