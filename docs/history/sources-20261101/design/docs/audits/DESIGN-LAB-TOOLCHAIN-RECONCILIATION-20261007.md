# 工具链与模型登记对账 · 2026-10-07

**观测 exact SHA**：`main` = `c15056f28b`（`gh api commits/main` 实读）
**观察窗口**：2026-10-06T18:32Z（本机直连文件系统与 `--version`，未启动任何宿主 GUI）
**性质**：只登记实测事实。**不修改任何配置文件**，因为其中一项是许可声明，属 rights 人工门。

> 触发原因：一次并行只读审计给出"很多工具在盘上但没登记"的结论。本文件是我**自己重测**的结果。
> 结论是：该说法**大部分不成立**，但**有一处是真的**，而且比原报告说的更关键。

---

## 一、被推翻的三条

| 原断言 | 实测 | 判定 |
|---|---|---|
| `resvg 0.47.0 实测命中 pinned sha256 却无 locator 条目` | `design-lab/config/reconstruction-tools.json` 的 `renderers` 块里有 `resvgWindows` 与 `resvgLinux` **两条完整登记**：repository、version、asset、url、`archiveSha256`、`executableSha256`、license、storageClass、pathPolicy | **错**。条目存在且完整 |
| `Blender 4.2.0 实测可用，registry 反写 not installed` | 在声明根 `os-toolchain`（`D:/All projects/OS External Configuration`）下 `**/blender.exe` **零命中** | **未证实**。至少不在声明根内 |
| `MACHINE_INVENTORY 仍记 Adobe 为 PRESENT / 或记已卸载` | 全仓 `git ls-files` 里**不存在** `MACHINE_INVENTORY` 文件 | **无此文件**，该断言无从成立 |

我 glob 找不到 resvg 的原因也值得记下来：它按 `pathPolicy: "explicit-authorized-path-only"` 与
`storageClass: "Design External Configuration/toolchain"` 存放，**设计上就不该被自动发现**。
把"自动发现不到"读成"没登记"，是一次典型的仪器误读。

## 二、被证实的两条

| 断言 | 实测证据 |
|---|---|
| PS / AI 主程序在盘上（与"已卸载"类说法冲突） | `C:/Program Files/Adobe/Adobe Photoshop 2025/Photoshop.exe` 199,420,848 B；`.../Adobe Illustrator 2025/Support Files/Contents/Windows/Illustrator.exe` 54,557,120 B。**未启动、未调用 COM**，只看文件 |
| H3 / SDXL 等权重在盘上但未激活 | `Model library` 下 12 个 >50 MB 文件，含 `ComfyUI/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors` **20,970.4 MB**、`sd_xl_base_1.0.safetensors` 6,938.1 MB、`text_encoders/clip_g.safetensors` 2,778.7 MB、`vae/minimax_h3_video_vae_fp16.safetensors` 5,207.8 MB、`whisper/faster-whisper-large-v3-turbo/model.bin` 1,617.9 MB |

## 三、我此前转述错误的一处，需要单独更正

我在上一轮把"H3 证据矛盾"列为待你裁决项，说法是"`LOCAL_ENVIRONMENT.md` 说仍未加载或推理，
但历史证据目录的 webp/mp4 校验和吻合"。**这两句不矛盾**，是我把两件不同的事当成冲突：

`docs/LOCAL_ENVIRONMENT.md:25` 原文是
"**四组件固定来源全量校验已完成；仍未加载或推理，许可适用条件未确认，不开启 profile**"。
即：**校验和吻合（来源完整性）** 与 **未加载未推理（能力资格）** 是同一句话里的两半，
文档自己就把它们分开了。历史证据目录的 sha256 与 sidecar 吻合，恰好**印证**了前半句，
不构成对后半句的反驳。

该撤的撤：H3 没有"文档自相矛盾"问题。真正仍待实测的仍是它自己写明的"加载、资源峰值、输出"，
而那需要一次真实的宿主/推理会话。

## 四、唯一真实的登记缺口：ffmpeg

代码**确实**调用 ffmpeg：`src/design_lab/creative/media/__init__.py`、
`src/design_lab/runtime/doctor.py`、`integrations/adapter-registry.json`、
`design-lab/scripts/verify_adapter_matrix.py`、`design-lab/tests/test_doctor_evidence.py`。

但 `reconstruction-tools.json` 里 **ffmpeg 出现 0 次** —— 即它没有 resvg 那样的
版本 / URL / 哈希 / 许可 / storageClass 固定条目。一个被生产代码调用的外部可执行文件
没有可核验绑定，这是真缺口。

实测到的是：`os-toolchain` 根下 `ffmpeg.exe` 242,496,512 B，
`--version` 首行 `ffmpeg version 8.1.2-full_build-www.gyan.dev`。
同目录另有 136 KB 的 **scoop 垫片**，其 `--version` 输出是
`Shim: Could not determine if target is a GUI app. Assuming console.` —— 垫片不可信，
与已知坑一致。

**为什么我没有直接登记它**：gyan.dev 的 `full_build` 是 **GPL-3.0**（含外部库），
把它写进 `reconstruction-tools.json` 作为固定依赖，是一次**许可声明**；
而 `AUTHORITY.md` §9 与项目 Human Gate 规定 rights 未知不得 production-certify。
所以这一步属于你和 rights 人工门，不属于我顺手填字段。

决策所需的最小事实：

1. 采用哪个构建：`full_build`(GPL-3) / `essentials_build`(LGPL-2.1+) / 自编译 —— 直接决定许可结论；
2. 若采用，`storageClass` 归 `Design External Configuration/toolchain` 还是 CI ephemeral（resvg 两种都有先例）；
3. 是否接受"随附二进制许可 = GPL"对产品分发的连带影响，或改为运行时可选依赖 + 缺失时 fail-closed。

## 五、附带事实（供排期用，非结论）

- `node v24.18.0`（`os-toolchain/10-toolchains/scoop/apps/nodejs-lts/24.18.0`）实测 `--version` 正常；
  项目本地 `.venv` Python 为 3.13.14，与投影 `environmentFingerprint` 一致。
- `.project/paths.json` 只声明 4 个 `shared_inputs` 根，**没有任何工具级条目**；
  工具固定信息一律在 `design-lab/config/reconstruction-tools.json`。因此"把缺的工具下载到声明库根"
  这件事，正确落点是 `reconstruction-tools.json`（含哈希与许可），而不是 `paths.json`。
