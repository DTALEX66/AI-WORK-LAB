# ASR 本地 CPU 转写与静音误识别对照审计

结论：真实 CPU 转写已执行；VAD 对照实验 PASS，独立读回 195 项 PASS。原始无 VAD 测试仍为 PARTIAL，失败原件不变。R3-08 整项和 host_live 均为 PARTIAL：OCR det＋rec、其他软件启动及产品资格接入未完成。不是 TTS、GPU、H3、自然录音基准或发布验收。

## 来源、环境与边界

- 复用用户模型库 `D:/All projects/Model library/whisper/faster-whisper-large-v3-turbo/`，未下载或复制权重。固定来源为 [dropbox-dash revision 0a363e91](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo/tree/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf)。五文件 size/SHA256 匹配，四个非 LFS 文件另核固定来源 Git blob SHA1。完整数值见下面 preparation；model.bin 为 1,617,884,929 字节，SHA256 `e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da`。
- 新建专用环境 `.project-local/task-runtime/asr-qualification/20260906T195532284136Z/venv/`；Python 3.13.14，faster-whisper 1.2.1、CTranslate2 4.8.2、ONNX Runtime 1.29.0、PyAV 18.1.0、NumPy 2.5.3、psutil 7.2.2。安装报告记录实际 wheel URL/hash，pip check 与真实导入通过。未在主 venv 或 ComfyUI 环境安装依赖。
- CPU INT8、4 线程、1 worker、beam_size=5、temperature=0、condition_on_previous_text=false；直接本地路径加载，offline，消费全部 segments。没有传 initial_prompt、hotwords 或参考答案。
- 英文/中文音频由本机已安装的 Microsoft Zira / Huihui Desktop 离线合成，自编设计短句；16000 Hz、mono、PCM16。未读取私人录音、录制麦克风、播放音频或调用云转写。System.Speech 只生成测试输入，不作为 DESIGN-LAB TTS 产品验收。
- Silero VAD 随专用环境的 faster-whisper 包提供；`silero_vad_v6.onnx` 为 1,245,151 字节，SHA256 `4cbf549b8326f60f80f2536d9eefeb450a9abe83365a098031c89719f1be17d2`。VAD/转写源码及 ONNX 字节与安装 RECORD 匹配；这是本地包完整性绑定，不是额外签署模型 trust。
- 临时、缓存、音频、结果均在本项目 `.project-local/`；Python audit hook 记录中无 socket connect、无越界写入拒绝。该观察不是 OS/DLL 级全系统追踪。执行前后五个 ASR 模型文件 hash 一致；未改生产源码、profile 或 trust。

## 原始测试：保留失败

2026-09-06T20:00:30Z（本地 09-07 04:00），独立环境模型加载 2.454 秒；英文 5.715 秒音频转写耗时 5.315 秒，中文 8.6 秒音频耗时 5.531 秒。规范化大小写/标点后的英文 WER、中文 CER 均为 0，未做繁简替换。损坏媒体抛出 InvalidDataError。

但两秒全零 PCM 静音被识别为 `Thank you.`；原始 `results.json` 保持 PARTIAL，运行句柄最终 exit 1。不是模型不存在、环境缺包，也不能被正向样例掩盖。旧终端输出存在中文编码显示问题，UTF-8 JSON 中文完整；没有因此重写原日志。

## 单变量对照：vad_filter=False / True

对照于 2026-09-06T20:09:00Z 结束，进程 exit 0。模型/解码参数不变，只切换内置 VAD（参数用本次安装版本默认值）。7 条样例、14 次真实调用，另有两次损坏媒体拒绝。协议和 0.20 错误率阈值在加载前写入，未事后改阈值。

| 输入 | 无 VAD | 开 VAD | 开 VAD 耗时 |
|---|---|---|---:|
| 英文原句 | PASS，WER 0 | PASS，WER 0 | 5.177 秒 |
| 中文原句 | PASS，CER 0 | PASS，CER 0 | 5.602 秒 |
| 全零静音，en | FAIL，`Thank you.` | PASS，空文本/保留时长 0 | 0.016 秒 |
| 全零静音，zh | FAIL，虚构中英混合字幕 | PASS，空文本/保留时长 0 | 0.015 秒 |
| 英文前后各两秒静音 | PASS，WER 0 | PASS，WER 0；保留 5.632 秒 | 5.121 秒 |
| 中文 PCM 振幅缩至 0.1 | PASS，CER 0 | PASS，CER 0 | 5.275 秒 |
| 两秒低幅随机噪声 | FAIL，`You` | PASS，空文本/保留时长 0 | 0.017 秒 |

损坏 WAV 两种设置均抛出 InvalidDataError。模型加载 2.274 秒；该进程 Windows peak working set 为 2,000,048,128 字节，覆盖本轮加载/调用，不是系统总内存或 GPU 峰值。两轮样本不构成严谨冷/热性能基准。

## 原因定位与下一实现约束

原调用显式 `vad_filter=False`，全零 PCM 因而进入自回归解码。实测静音的 `no_speech_prob` 约 `8.45e-11`，低于默认 0.6；模型自身该概率未能识别静音。当前安装源码还会在平均 logprob 足够高时保留解码结果，因此不能仅凭该字段判断“有真实讲话”。不是文本编码或参考答案泄漏导致。

[上游 v1.2.1 文档](https://github.com/SYSTRAN/faster-whisper/tree/v1.2.1)提供内置 VAD；本地源码确认它在解码前选择语音区间。A/B 显示 VAD 将本组非语音剔除，同时保留了正向文字。但这是受控样例结果，不能外推到所有静音/噪声、极低音量、口音、多人或自然录音。

后续产品 ASR 接入必须绑定 VAD 版本/hash/参数及真实转写证据；区分无语音、解码失败、模型不可用和成功转写。不得以固定文本黑名单（如删除 Thank you）修补症状，不得把空转写包装成有内容的成功。生产 resolver 仍保持未资格状态，尚未实现这条产品转写链。下一项是 R3-08 的 OCR det＋rec 实测及就绪证据接入。

## 人工审计入口与复核

所有运行材料为本地 ignored 证据，换机缺失须报 MISSING，不能重建假日志。

- [固定来源、五文件完整 hash 与准备结果](../../.project-local/task-artifacts/asr-qualification/20260906T195532284136Z/preparation.json)
- [实际 wheel 安装报告](../../.project-local/task-artifacts/asr-qualification/20260906T195532284136Z/install-report.json)
- [英文输入](../../.project-local/task-artifacts/asr-qualification/20260906T195532284136Z/english.wav) / [中文输入](../../.project-local/task-artifacts/asr-qualification/20260906T195532284136Z/chinese.wav)
- [原始失败结果](../../.project-local/task-artifacts/asr-qualification/20260906T195532284136Z/inference-20260906T200010211099Z/results.json)
- [预先固定的对照协议](../../.project-local/task-artifacts/asr-qualification/20260906T195532284136Z/vad-comparison-20260906T200758490223Z/protocol.json)
- [完整对照结果与逐段概率/时间](../../.project-local/task-artifacts/asr-qualification/20260906T195532284136Z/vad-comparison-20260906T200758490223Z/results.json)
- [独立 195 项读回](../../.project-local/task-artifacts/asr-qualification/20260906T195532284136Z/vad-comparison-20260906T200758490223Z/independent-20260906T201031872880Z.json)

独立核验检查文件/hash、PCM 变换、全零静音、完整 A/B 矩阵、文本与 segments 一致性、独立编辑距离、时间戳、原 FAIL 保留和输入模型前后不变。195 项检查不是 195 次模型推理，也不把对照中的三个预期 FAIL 改成 PASS。

实际命令（在项目根）：

```powershell
& '.project-local/task-runtime/asr-qualification/20260906T195532284136Z/venv/Scripts/python.exe' -I -B '.project-local/task-artifacts/asr-qualification/vad_comparison.py'
& '.venv/Scripts/python.exe' -I -B '.project-local/task-artifacts/asr-qualification/verify_vad_comparison.py' 'D:/All projects/DESIGN-LAB/.project-local/task-artifacts/asr-qualification/20260906T195532284136Z/vad-comparison-20260906T200758490223Z'
```

本轮只读查验后复用准备环境；没有重跑安装。此前 urllib TLS EOF/固定目录已存在的旧断点已由独立新 run 与可用 HTTPS 客户端绕开，不禁用 TLS、不删除旧现场。取消/回退只需停止自有诊断进程，本轮进程已正常结束；未演示生产取消/恢复。

HEAD `c4dccd58331bc4561eb89265283d924b7630d113` 不是未提交工作树的完整快照，receipt 绑定具体文件哈希。未 commit/push/PR/发布，未代签 Human Gate；知识迁移继续延后。
