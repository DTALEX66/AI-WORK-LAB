# 开源与成熟项目吸收池

> 只读审计 / 2026-09-29 / current main `010f6a57610214fa41651861e00319f88a2f49a4`。本文是审计与候选方案，不是新 Authority，也不是第二份可编辑任务账本。历史完整性：**未完成**；Windows 实机复测：**本轮未执行**。

## 推荐顺序与准入

先吸收已成熟的技术能力，再补领域语义。近期优先：axe-core 检测、DTCG/Style Dictionary、资产上传及预览 primitives；对 Spectrum Web Components 和 Web Awesome 做同一 10 控件试验。Spectrum 属于专业创作工具风格且框架无关，但 Lit/Shadow DOM、CSP 与当前 IIFE/静态打包必须验证；Web Awesome 的免费 MIT 与 Pro 资源不可混为一个许可。Fluent 适合 Windows 交互参考，不自动意味着必须换成 WinUI。React Aria/shadcn 有价值，但当前并非 React 项目。不要把“已有25类CSS覆盖”误判为完整键盘/读屏/状态成熟度。

Avalonia/WinUI/Tauri/Electron 均为部署路线候选，当前先保持 web 工作台；待确有托盘、文件关联、离线分发等需求才做 ADR。Penpot/OpenPencil/Open Design 是外部宿主或 UX donor；不能复制成第二画布。tldraw 为定制许可，IQA-PyTorch 本次pin为非商用许可，都不能按“开源=可商用”处理。

所有 pin 是本次查询得到的上游提交，**不是 DESIGN-LAB 已吸收的版本**。下面 Windows 表示候选技术可行性而非本机认证。无 Windows/GPU 性能数值是因为本轮没有执行基准。供应商网页产品（Adobe、Figma、MiniMax Design、Eagle）另见适配矩阵；开源代码许可证不覆盖模型权重、字体、云服务、安装包或商业资产。

## 基准协议（均待执行）

| 协议 | 验收输入与指标 | 退出/回滚 |
| --- | --- | --- |
| B-UI | Button/Input/Select/Dialog/Menu/Tree/Table/Toast/Tabs/Popover；中文IME、键盘、读屏、高对比、错误/空/加载/禁用；当前CSP与Python wheel安装后运行；包体/冷启动测量 | 不通过关键无障碍或CSP则保留当前控件 |
| B-ASSET | 1000项浏览、不同尺寸/损坏/重复/未授权文件、部分失败、路径安全、缩略图内存 | 禁用新浏览器，资产记录不丢 |
| B-TOKEN | 当前DTCG fixture往返、别名/模式/单位、无损diff、旧版本还原 | 同schema可回退 |
| B-HOST | 同真实Brief，创建→两次局部改动→readback→重开→回滚；源文件可编辑 | 保留before副本、明确手工接管 |
| B-COMFY | 固定workflow/model/hash/seed；10次运行、断连、cancel ACK、输出hash、WS/history一致 | 独立实例关闭，既有用户实例不动 |
| B-MODEL | 同授权任务集与固定版本；显存峰值/时延/成功率/字体伪影/独立盲评；无伪造分数 | 模型可替换，生成物来源不丢 |
| B-INTEROP | 色彩/材质/时间线/场景往返、丢失字段清单、宿主重开 | 回退原始宿主文件 |
| B-SHELL | 安装/升级/卸载、文件关联、启动失败、低权限、离线、本地服务端口和更新签名 | 浏览器入口可独立运行 |
| B-PREVIEW / B-TOOL | 大图缩放/选区/坐标/异常输入、取消和临时文件清理 | 只读预览或手动工具 |

## 本轮候选逐项卡片

### AcademySoftwareFoundation/MaterialX


| 字段 | 值 |
| --- | --- |
| project | AcademySoftwareFoundation/MaterialX |
| url | https://github.com/AcademySoftwareFoundation/MaterialX |
| sha | 8920a4f162ebcd7c925eff9c715793d4dc0acf81 |
| license | Apache-2.0 |
| capability | 色彩/时间线/材质/场景互操作 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | ALGORITHM_DONOR |
| boundary | 按宿主格式适配，不作为新的编辑器 |
| fallback | 手动操作/现有工具 |
| benchmark | B-INTEROP（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### AcademySoftwareFoundation/OpenColorIO


| 字段 | 值 |
| --- | --- |
| project | AcademySoftwareFoundation/OpenColorIO |
| url | https://github.com/AcademySoftwareFoundation/OpenColorIO |
| sha | eb25aaad6607f0a551de40063174a47324c93888 |
| license | BSD-3-Clause |
| capability | 色彩/时间线/材质/场景互操作 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | ALGORITHM_DONOR |
| boundary | 按宿主格式适配，不作为新的编辑器 |
| fallback | 手动操作/现有工具 |
| benchmark | B-INTEROP（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### AcademySoftwareFoundation/OpenTimelineIO


| 字段 | 值 |
| --- | --- |
| project | AcademySoftwareFoundation/OpenTimelineIO |
| url | https://github.com/AcademySoftwareFoundation/OpenTimelineIO |
| sha | dc8366533acd6730228a9802b7cc7a8b6439d2ef |
| license | Apache-2.0 |
| capability | 色彩/时间线/材质/场景互操作 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | ALGORITHM_DONOR |
| boundary | 按宿主格式适配，不作为新的编辑器 |
| fallback | 手动操作/现有工具 |
| benchmark | B-INTEROP（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### AvaloniaUI/Avalonia


| 字段 | 值 |
| --- | --- |
| project | AvaloniaUI/Avalonia |
| url | https://github.com/AvaloniaUI/Avalonia |
| sha | bc4d4396488b6b6b19b7fb81c74805cc84c12ac5 |
| license | MIT |
| capability | 桌面壳/原生UI |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 不需专用GPU |
| integration_mode | DEFERRED |
| boundary | 部署外壳，不搬运领域Authority |
| fallback | 浏览器工作台 |
| benchmark | B-SHELL（方案，未运行） |
| rollback | 保留同一Python服务与项目数据 |

### Comfy-Org/ComfyUI


| 字段 | 值 |
| --- | --- |
| project | Comfy-Org/ComfyUI |
| url | https://github.com/Comfy-Org/ComfyUI |
| sha | a7169322485d0049380fb207fa17e9fb3ec40486 |
| license | GPL-3.0 |
| capability | 图像/视频/3D工作流执行 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 模型相关；空图工作流不需证明模型可用 |
| integration_mode | SIDECAR |
| boundary | 设计任务提交/取消/回读，不管理全局Agent |
| fallback | 手动操作/现有工具 |
| benchmark | B-COMFY（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### FFmpeg/FFmpeg


| 字段 | 值 |
| --- | --- |
| project | FFmpeg/FFmpeg |
| url | https://github.com/FFmpeg/FFmpeg |
| sha | 3116ce4f3e4b6323dfc3d8a2437affceed80176e |
| license | LGPL-2.1-or-later为主；启用组件可改变许可 |
| capability | 专业设计辅助工具 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | TOOL_PROVIDER |
| boundary | 只暴露设计域能力 |
| fallback | 手动操作/现有工具 |
| benchmark | B-TOOL（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### MiniMax-AI/MiniMax-H3


| 字段 | 值 |
| --- | --- |
| project | MiniMax-AI/MiniMax-H3 |
| url | https://github.com/MiniMax-AI/MiniMax-H3 |
| sha | d21241f0a4b3acbb34c97dae47fa417b7065e438 |
| license | 代码/权重分开；HF Community License；下载前复核 |
| capability | 推理能力（图像/视频/3D或模型服务） |
| windows | 候选可行；本轮未在Windows实测 |
| local | 模型/运行时部分可本地；H3全链含hosted IR |
| gpu | 取决模型/量化/尺寸，未做显存基准 |
| integration_mode | MODEL_PROVIDER |
| boundary | 不成为默认依赖或全局模型网关 |
| fallback | 用户已有云服务或手工素材 |
| benchmark | B-MODEL（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### MiniMax-AI/minimax-desgin-plugin


| 字段 | 值 |
| --- | --- |
| project | MiniMax-AI/minimax-desgin-plugin |
| url | https://github.com/MiniMax-AI/minimax-desgin-plugin |
| sha | bef9de2101e9d873619c83553b8f03ebb0c10663 |
| license | 未取得明确根LICENSE；吸收/分发前BLOCKED |
| capability | 官方Comfy适配插件（仓名desgin） |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | TOOL_PROVIDER |
| boundary | 只暴露设计域能力 |
| fallback | 手动操作/现有工具 |
| benchmark | B-COMFY（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### MiniMax-design-H3/minimax-design


| 字段 | 值 |
| --- | --- |
| project | MiniMax-design-H3/minimax-design |
| url | https://github.com/MiniMax-design-H3/minimax-design |
| sha | 684390616d071250ed482932e6540a807d48d394 |
| license | MIT；不覆盖产品与模型 |
| capability | 外部编辑宿主/客户端 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 宿主/任务相关 |
| integration_mode | REFERENCE |
| boundary | 未从官方站点证实该仓归属，禁止当官方安装源 |
| fallback | 文件handoff或现有Adobe |
| benchmark | B-HOST（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### PaddlePaddle/PaddleOCR


| 字段 | 值 |
| --- | --- |
| project | PaddlePaddle/PaddleOCR |
| url | https://github.com/PaddlePaddle/PaddleOCR |
| sha | dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf |
| license | UNKNOWN |
| capability | 专业设计辅助工具 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | TOOL_PROVIDER |
| boundary | 只暴露设计域能力 |
| fallback | 手动操作/现有工具 |
| benchmark | B-TOOL（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### PixarAnimationStudios/OpenUSD


| 字段 | 值 |
| --- | --- |
| project | PixarAnimationStudios/OpenUSD |
| url | https://github.com/PixarAnimationStudios/OpenUSD |
| sha | 2a9a571d0f9957bad5c4a59ba859ebb8df518c51 |
| license | NOASSERTION |
| capability | 色彩/时间线/材质/场景互操作 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | ALGORITHM_DONOR |
| boundary | 按宿主格式适配，不作为新的编辑器 |
| fallback | 手动操作/现有工具 |
| benchmark | B-INTEROP（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### QwenLM/Qwen-Image


| 字段 | 值 |
| --- | --- |
| project | QwenLM/Qwen-Image |
| url | https://github.com/QwenLM/Qwen-Image |
| sha | 6b5e1f5cec987d404be5ac6657db3b9aacb56a89 |
| license | Apache-2.0 |
| capability | 推理能力（图像/视频/3D或模型服务） |
| windows | 候选可行；本轮未在Windows实测 |
| local | 模型/运行时部分可本地；H3全链含hosted IR |
| gpu | 取决模型/量化/尺寸，未做显存基准 |
| integration_mode | MODEL_PROVIDER |
| boundary | 不成为默认依赖或全局模型网关 |
| fallback | 用户已有云服务或手工素材 |
| benchmark | B-MODEL（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### Tencent-Hunyuan/Hunyuan3D-2


| 字段 | 值 |
| --- | --- |
| project | Tencent-Hunyuan/Hunyuan3D-2 |
| url | https://github.com/Tencent-Hunyuan/Hunyuan3D-2 |
| sha | f8db63096c8282cb27354314d896feba5ba6ff8a |
| license | Tencent Hunyuan 3D 2.0 Community；地域/用途限制需审核 |
| capability | 推理能力（图像/视频/3D或模型服务） |
| windows | 候选可行；本轮未在Windows实测 |
| local | 模型/运行时部分可本地；H3全链含hosted IR |
| gpu | 取决模型/量化/尺寸，未做显存基准 |
| integration_mode | MODEL_PROVIDER |
| boundary | 不成为默认依赖或全局模型网关 |
| fallback | 用户已有云服务或手工素材 |
| benchmark | B-MODEL（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### Wan-Video/Wan2.2


| 字段 | 值 |
| --- | --- |
| project | Wan-Video/Wan2.2 |
| url | https://github.com/Wan-Video/Wan2.2 |
| sha | 1ea34ff48f87168174e12956e200b1d908b1c5ff |
| license | Apache-2.0 |
| capability | 推理能力（图像/视频/3D或模型服务） |
| windows | 候选可行；本轮未在Windows实测 |
| local | 模型/运行时部分可本地；H3全链含hosted IR |
| gpu | 取决模型/量化/尺寸，未做显存基准 |
| integration_mode | MODEL_PROVIDER |
| boundary | 不成为默认依赖或全局模型网关 |
| fallback | 用户已有云服务或手工素材 |
| benchmark | B-MODEL（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### adobe/react-spectrum


| 字段 | 值 |
| --- | --- |
| project | adobe/react-spectrum |
| url | https://github.com/adobe/react-spectrum |
| sha | 17334738e8180cf33f8bbaa88c57d8ba6b66f24a |
| license | Apache-2.0 |
| capability | UI primitives / 设计系统交互 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 不需专用GPU |
| integration_mode | EVALUATE |
| boundary | 当前strictTS工作台内局部组件；React库需ADR |
| fallback | 当前组件 |
| benchmark | B-UI（方案，未运行） |
| rollback | feature flag退回原组件 |

### adobe/spectrum-web-components


| 字段 | 值 |
| --- | --- |
| project | adobe/spectrum-web-components |
| url | https://github.com/adobe/spectrum-web-components |
| sha | d6cb9ba9c11dfb987f02b1fd9c20aa2de1a58e11 |
| license | Apache-2.0 |
| capability | UI primitives / 设计系统交互 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 不需专用GPU |
| integration_mode | EVALUATE |
| boundary | 当前strictTS工作台内局部组件；React库需ADR |
| fallback | 当前组件 |
| benchmark | B-UI（方案，未运行） |
| rollback | feature flag退回原组件 |

### amzn/style-dictionary


| 字段 | 值 |
| --- | --- |
| project | amzn/style-dictionary |
| url | https://github.com/amzn/style-dictionary |
| sha | 951cc612b37a18f2d26fcfa55858c93b09109e1d |
| license | Apache-2.0 |
| capability | Design Tokens规范/编译 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | ADOPT |
| boundary | 复用现有DTCG converter，不新建格式 |
| fallback | 手动操作/现有工具 |
| benchmark | B-TOKEN（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### blender/blender


| 字段 | 值 |
| --- | --- |
| project | blender/blender |
| url | https://github.com/blender/blender |
| sha | cd135abc53f043bf2ca9d762107662a22d8491e2 |
| license | GPL；具体子目录及再分发条款分别核对 |
| capability | 外部编辑宿主/客户端 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 宿主/任务相关 |
| integration_mode | HOST_ADAPTER |
| boundary | 源文件由宿主持有；WORK可管理外部客户端状态 |
| fallback | 文件handoff或现有Adobe |
| benchmark | B-HOST（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### chaiNNer-org/chaiNNer


| 字段 | 值 |
| --- | --- |
| project | chaiNNer-org/chaiNNer |
| url | https://github.com/chaiNNer-org/chaiNNer |
| sha | b3ca7ff586d4071dbe8601bc4000493560503f21 |
| license | UNKNOWN |
| capability | 专业设计辅助工具 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | TOOL_PROVIDER |
| boundary | 只暴露设计域能力 |
| fallback | 手动操作/现有工具 |
| benchmark | B-TOOL（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### chaofengc/IQA-PyTorch


| 字段 | 值 |
| --- | --- |
| project | chaofengc/IQA-PyTorch |
| url | https://github.com/chaofengc/IQA-PyTorch |
| sha | 6e48c5ca9e3e58bd632af52f06a2ca976ccf2722 |
| license | PolyForm Noncommercial（本次pin；商业吸收BLOCKED） |
| capability | 图像质量指标/算法参考 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | BLOCKED |
| boundary | 指标只辅助，不替代专业Jury；本pin非商用许可 |
| fallback | 手动操作/现有工具 |
| benchmark | B-TOOL（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### dequelabs/axe-core


| 字段 | 值 |
| --- | --- |
| project | dequelabs/axe-core |
| url | https://github.com/dequelabs/axe-core |
| sha | 24736a4f3df243c1de692f17dd0e1e3d23a4542d |
| license | MPL-2.0 |
| capability | 可访问性自动检测 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | ADOPT |
| boundary | 自动检测不能替代键盘/读屏人工验收 |
| fallback | 手动操作/现有工具 |
| benchmark | B-UI（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### design-tokens/community-group


| 字段 | 值 |
| --- | --- |
| project | design-tokens/community-group |
| url | https://github.com/design-tokens/community-group |
| sha | 882ebd6716abef9a46d8ef5fb12e82009d6cee2e |
| license | W3C Software and Document License（规范） |
| capability | Design Tokens规范/编译 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | ADOPT |
| boundary | 复用现有DTCG converter，不新建格式 |
| fallback | 手动操作/现有工具 |
| benchmark | B-TOKEN（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### dimsemenov/PhotoSwipe


| 字段 | 值 |
| --- | --- |
| project | dimsemenov/PhotoSwipe |
| url | https://github.com/dimsemenov/PhotoSwipe |
| sha | cd41cb587a460634e4cae53134f3d01d06e284a6 |
| license | MIT |
| capability | 资产导入/预览 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | EVALUATE |
| boundary | 只暴露设计域能力 |
| fallback | 手动操作/现有工具 |
| benchmark | B-ASSET（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### electron/electron


| 字段 | 值 |
| --- | --- |
| project | electron/electron |
| url | https://github.com/electron/electron |
| sha | 2454be571a6a12d83206d83882ffc91fe5335cdc |
| license | MIT |
| capability | 桌面壳/原生UI |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 不需专用GPU |
| integration_mode | DEFERRED |
| boundary | 部署外壳，不搬运领域Authority |
| fallback | 浏览器工作台 |
| benchmark | B-SHELL（方案，未运行） |
| rollback | 保留同一Python服务与项目数据 |

### fabricjs/fabric.js


| 字段 | 值 |
| --- | --- |
| project | fabricjs/fabric.js |
| url | https://github.com/fabricjs/fabric.js |
| sha | 013b48a325255b3b0663595582c4017ea853e887 |
| license | MIT |
| capability | 选择/缩放/预览等图形交互 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | UX_DONOR |
| boundary | 可借局部预览；完整第二画布REJECT_CORE |
| fallback | 静态预览+打开宿主 |
| benchmark | B-PREVIEW（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### konvajs/konva


| 字段 | 值 |
| --- | --- |
| project | konvajs/konva |
| url | https://github.com/konvajs/konva |
| sha | ca62a92ee60095803bf69abae29d92b936ee2eef |
| license | MIT |
| capability | 选择/缩放/预览等图形交互 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | UX_DONOR |
| boundary | 可借局部预览；完整第二画布REJECT_CORE |
| fallback | 静态预览+打开宿主 |
| benchmark | B-PREVIEW（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### lit/lit


| 字段 | 值 |
| --- | --- |
| project | lit/lit |
| url | https://github.com/lit/lit |
| sha | 01dbc6673cdc211543932afd0ca04e223e567366 |
| license | BSD-3-Clause |
| capability | UI primitives / 设计系统交互 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 不需专用GPU |
| integration_mode | EVALUATE |
| boundary | 当前strictTS工作台内局部组件；React库需ADR |
| fallback | 当前组件 |
| benchmark | B-UI（方案，未运行） |
| rollback | feature flag退回原组件 |

### microsoft/fluentui


| 字段 | 值 |
| --- | --- |
| project | microsoft/fluentui |
| url | https://github.com/microsoft/fluentui |
| sha | 45af037915bae19733ffb8cb2123d8e6e216e881 |
| license | MIT |
| capability | UI primitives / 设计系统交互 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 不需专用GPU |
| integration_mode | EVALUATE |
| boundary | 当前strictTS工作台内局部组件；React库需ADR |
| fallback | 当前组件 |
| benchmark | B-UI（方案，未运行） |
| rollback | feature flag退回原组件 |

### microsoft/microsoft-ui-xaml


| 字段 | 值 |
| --- | --- |
| project | microsoft/microsoft-ui-xaml |
| url | https://github.com/microsoft/microsoft-ui-xaml |
| sha | c5044a7197b7483335c36dd6f4336ac8f3202866 |
| license | MIT |
| capability | 桌面壳/原生UI |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 不需专用GPU |
| integration_mode | DEFERRED |
| boundary | 部署外壳，不搬运领域Authority |
| fallback | 浏览器工作台 |
| benchmark | B-SHELL（方案，未运行） |
| rollback | 保留同一Python服务与项目数据 |

### modelcontextprotocol/inspector


| 字段 | 值 |
| --- | --- |
| project | modelcontextprotocol/inspector |
| url | https://github.com/modelcontextprotocol/inspector |
| sha | 1e31c78fbf81a989e8eb47021c6281d7876ad7fd |
| license | 本次LICENSE声明MIT→Apache-2.0过渡；逐文件审核 |
| capability | MCP协议诊断 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | SIDECAR |
| boundary | 仅设计适配器端点；全局服务器管理归WORK |
| fallback | 手动操作/现有工具 |
| benchmark | B-TOOL（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### nexu-io/open-design


| 字段 | 值 |
| --- | --- |
| project | nexu-io/open-design |
| url | https://github.com/nexu-io/open-design |
| sha | 5b19dfa4351b3eed33826ee72746a7c653c23a54 |
| license | Apache-2.0 |
| capability | 外部编辑宿主/客户端 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 宿主/任务相关 |
| integration_mode | HOST_ADAPTER |
| boundary | 源文件由宿主持有；WORK可管理外部客户端状态 |
| fallback | 文件handoff或现有Adobe |
| benchmark | B-HOST（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### ollama/ollama


| 字段 | 值 |
| --- | --- |
| project | ollama/ollama |
| url | https://github.com/ollama/ollama |
| sha | a8aaf9fcfad23dc8d6f07b8109b1ba5ed310d76c |
| license | MIT |
| capability | 推理能力（图像/视频/3D或模型服务） |
| windows | 候选可行；本轮未在Windows实测 |
| local | 模型/运行时部分可本地；H3全链含hosted IR |
| gpu | 取决模型/量化/尺寸，未做显存基准 |
| integration_mode | MODEL_PROVIDER |
| boundary | 不成为默认依赖或全局模型网关 |
| fallback | 用户已有云服务或手工素材 |
| benchmark | B-MODEL（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### open-pencil/open-pencil


| 字段 | 值 |
| --- | --- |
| project | open-pencil/open-pencil |
| url | https://github.com/open-pencil/open-pencil |
| sha | b0231927c509340682052527726b2058428e96ce |
| license | MIT |
| capability | 外部编辑宿主/客户端 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 宿主/任务相关 |
| integration_mode | HOST_ADAPTER |
| boundary | 源文件由宿主持有；WORK可管理外部客户端状态 |
| fallback | 文件handoff或现有Adobe |
| benchmark | B-HOST（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### penpot/penpot


| 字段 | 值 |
| --- | --- |
| project | penpot/penpot |
| url | https://github.com/penpot/penpot |
| sha | eb2576b8c03d59b9049a754a190299edc9c58a95 |
| license | MPL-2.0 |
| capability | 外部编辑宿主/客户端 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 宿主/任务相关 |
| integration_mode | HOST_ADAPTER |
| boundary | 源文件由宿主持有；WORK可管理外部客户端状态 |
| fallback | 文件handoff或现有Adobe |
| benchmark | B-HOST（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### retejs/rete


| 字段 | 值 |
| --- | --- |
| project | retejs/rete |
| url | https://github.com/retejs/rete |
| sha | 2aae19950180dc12725306f06c0440f64473bd21 |
| license | MIT |
| capability | 节点图UI |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | EVALUATE |
| boundary | 仅设计域流程可视化，不写通用调度runtime |
| fallback | 手动操作/现有工具 |
| benchmark | B-UI（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### shadcn-ui/ui


| 字段 | 值 |
| --- | --- |
| project | shadcn-ui/ui |
| url | https://github.com/shadcn-ui/ui |
| sha | db2db460a26fa84fb65c8d903b213925fbdee9ed |
| license | MIT |
| capability | UI primitives / 设计系统交互 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 不需专用GPU |
| integration_mode | EVALUATE |
| boundary | 当前strictTS工作台内局部组件；React库需ADR |
| fallback | 当前组件 |
| benchmark | B-UI（方案，未运行） |
| rollback | feature flag退回原组件 |

### shoelace-style/webawesome


| 字段 | 值 |
| --- | --- |
| project | shoelace-style/webawesome |
| url | https://github.com/shoelace-style/webawesome |
| sha | 2603978df2137d6ac37480a3a615a9f764b2864a |
| license | MIT |
| capability | UI primitives / 设计系统交互 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 不需专用GPU |
| integration_mode | EVALUATE |
| boundary | 当前strictTS工作台内局部组件；React库需ADR |
| fallback | 当前组件 |
| benchmark | B-UI（方案，未运行） |
| rollback | feature flag退回原组件 |

### storybooks/storybook


| 字段 | 值 |
| --- | --- |
| project | storybooks/storybook |
| url | https://github.com/storybooks/storybook |
| sha | 6a0469cb33e7d7bfab6f651c0d0d0c82926e465d |
| license | MIT |
| capability | UI primitives / 设计系统交互 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 不需专用GPU |
| integration_mode | EVALUATE |
| boundary | 当前strictTS工作台内局部组件；React库需ADR |
| fallback | 当前组件 |
| benchmark | B-UI（方案，未运行） |
| rollback | feature flag退回原组件 |

### tauri-apps/tauri


| 字段 | 值 |
| --- | --- |
| project | tauri-apps/tauri |
| url | https://github.com/tauri-apps/tauri |
| sha | d15cf9b1e481035a248227c791fde5740fcfe0ba |
| license | API标Apache-2.0；双许可范围须核对实际子包 |
| capability | 桌面壳/原生UI |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 不需专用GPU |
| integration_mode | DEFERRED |
| boundary | 部署外壳，不搬运领域Authority |
| fallback | 浏览器工作台 |
| benchmark | B-SHELL（方案，未运行） |
| rollback | 保留同一Python服务与项目数据 |

### tldraw/tldraw


| 字段 | 值 |
| --- | --- |
| project | tldraw/tldraw |
| url | https://github.com/tldraw/tldraw |
| sha | fdd9b4dee0d968cb92b52db2b6e0d37ffc906d74 |
| license | tldraw custom license；生产条款需审核 |
| capability | 选择/缩放/预览等图形交互 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | UX_DONOR |
| boundary | 可借局部预览；完整第二画布REJECT_CORE |
| fallback | 静态预览+打开宿主 |
| benchmark | B-PREVIEW（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### transloadit/uppy


| 字段 | 值 |
| --- | --- |
| project | transloadit/uppy |
| url | https://github.com/transloadit/uppy |
| sha | 41edd0f96a450616431cec1e57c2cb70e7c1a9e7 |
| license | MIT |
| capability | 资产导入/预览 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | EVALUATE |
| boundary | 只暴露设计域能力 |
| fallback | 手动操作/现有工具 |
| benchmark | B-ASSET（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### veraPDF/veraPDF-library


| 字段 | 值 |
| --- | --- |
| project | veraPDF/veraPDF-library |
| url | https://github.com/veraPDF/veraPDF-library |
| sha | 91b2cf8cca3b7a246765d0c58df74d0c223df874 |
| license | UNKNOWN |
| capability | PDF/A等标准验证 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | TOOL_PROVIDER |
| boundary | 不等价于全部印刷preflight；未知许可先复核 |
| fallback | 手动操作/现有工具 |
| benchmark | B-TOOL（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### visioncortex/vtracer


| 字段 | 值 |
| --- | --- |
| project | visioncortex/vtracer |
| url | https://github.com/visioncortex/vtracer |
| sha | dfd94865569b9cc0283219bb6309f8568caeea2b |
| license | MIT |
| capability | 专业设计辅助工具 |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | TOOL_PROVIDER |
| boundary | 只暴露设计域能力 |
| fallback | 手动操作/现有工具 |
| benchmark | B-TOOL（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

### xyflow/xyflow


| 字段 | 值 |
| --- | --- |
| project | xyflow/xyflow |
| url | https://github.com/xyflow/xyflow |
| sha | 3d35b57317576b0916c0bfeaaedd573aaacc2839 |
| license | MIT |
| capability | 节点图UI |
| windows | 候选可行；本轮未在Windows实测 |
| local | 可本地 |
| gpu | 通常CPU；具体后端另测 |
| integration_mode | EVALUATE |
| boundary | 仅设计域流程可视化，不写通用调度runtime |
| fallback | 手动操作/现有工具 |
| benchmark | B-UI（方案，未运行） |
| rollback | 移除适配配置，保留项目与生成物 |

## 历史吸收池：全部保留

以下162项来自当前 QUARANTINE_REGISTRY。其旧 adopt-now/status 只保留为历史事实；当前仍是 quarantine，未自动授权激活。缺字段与原始记录全文在附录JSON。新研究命中同URL也不会自动清除旧人审门槛。


| sourceId | 项目 | URL | 旧integration | 旧status | 当前缺失字段 |
| --- | --- | --- | --- | --- | --- |
| od-upstream | Open Design | https://github.com/nexu-io/open-design | adapter | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| google-design-md | Google DESIGN.md | https://github.com/google-labs-code/design.md | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| dtcg | W3C Design Tokens Community Group | https://github.com/design-tokens/community-group | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| hallmark | Hallmark | https://github.com/nutlope/hallmark | derive | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| styleseed | StyleSeed | https://github.com/bitjaru/styleseed | derive | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| ux-skill | ux-skill | https://github.com/Laith0003/ux-skill | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| typeui | TypeUI | https://github.com/bergside/typeui | quarantine | review-required | author; license; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| awesome-design-skills | Awesome Design Skills | https://github.com/bergside/awesome-design-skills | quarantine | review-required | author; license; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| open-codesign | Open CoDesign | https://github.com/OpenCoworkAI/open-codesign | reference | reference-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| manalkaff-opendesign | OpenDesign portable skills | https://github.com/manalkaff/opendesign | quarantine | review-required | author; license; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| claude-design-skill | Claude Design Skill | https://github.com/jiji262/claude-design-skill | derive | review-required | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| brandmd | brandmd | https://github.com/yuvrajangadsingh/brandmd | quarantine | review-required | author; license; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| openskill-eval | OpenSkillEval | https://github.com/ALEX-nlp/OpenSkillEval | derive | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| critic-eval | CriticEval | https://github.com/open-compass/CriticEval | reference | review-required | author; license; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| skillcenter | SkillCenter paper | https://arxiv.org/abs/2607.07676 | derive | reference-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| semantic-skill-attacks | Semantic supply-chain attacks on SKILL.md | https://arxiv.org/abs/2605.11418 | derive | adopt-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| wcag22 | WCAG 2.2 | https://www.w3.org/TR/WCAG22/ | reference | adopt-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| aria-apg | ARIA Authoring Practices Guide | https://www.w3.org/WAI/ARIA/apg/ | derive | adopt-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| wcag-json | WCAG machine-readable JSON | https://www.w3.org/WAI/standards-guidelines/wcag/ | adapter | adapter-next | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| coga-wayfinding | W3C COGA Wayfinding | https://www.w3.org/TR/coga-wayfinding/ | derive | reference-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| govuk-principles | UK Government Design Principles | https://www.gov.uk/guidance/government-design-principles | derive | adopt-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| govuk-design-system | GOV.UK Design System | https://design-system.service.gov.uk/ | adapter | adapter-next | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| 18f-methods | 18F Methods | https://guides.18f.org/methods/about/ | vendor-adapt | adopt-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| 18f-ux-guide | 18F UX Guide | https://guides.18f.org/ux-guide/ | vendor-adapt | adopt-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| plain-language | DfE Plain Language Standard | https://standards.education.gov.uk/standard/plain-language | derive | adopt-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| smithsonian-exhibition | Smithsonian Accessible Exhibition Design | https://www.wbdg.org/ffc/smithsonian-guidelines-for-accessible-exhibition-design | derive | adopt-now | author; license; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| nps-exhibit-access | NPS Exhibit Accessibility Guidelines | https://www.nps.gov/features/hfc/guidelines/ | derive | adopt-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| ada-standards | ADA Standards for Accessible Design | https://www.ada.gov/law-and-regs/design-standards/ | reference | reference-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| carbon | IBM Carbon Design System | https://github.com/carbon-packages/design-system/carbon | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| material3 | Material Design 3 | https://m3.material.io/ | adapter | adapter-next | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| primer | GitHub Primer | https://github.com/primer/design | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| spectrum | Adobe Spectrum CSS | https://github.com/adobe/spectrum-css | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| fluent | Microsoft Fluent UI | https://github.com/microsoft/fluentui | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| polaris | Shopify Polaris | https://github.com/Shopify/polaris | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| uswds | U.S. Web Design System | https://github.com/uswds/uswds | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| cms-design-system | CMS Design System | https://design.cms.gov/ | reference | reference-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| ant-design | Ant Design | https://github.com/ant-design/ant-design | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| arco-design | Arco Design | https://github.com/arco-design/arco-design | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| tdesign | TDesign | https://github.com/Tencent/tdesign | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| semi-design | Semi Design | https://github.com/DouyinFE/semi-design | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| radix-ui | Radix UI Primitives | https://github.com/radix-ui/primitives | adapter | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| react-aria | React Aria | https://github.com/adobe/react-spectrum | adapter | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| ark-ui | Ark UI | https://github.com/chakra-ui/ark | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| zag | Zag.js | https://github.com/chakra-ui/zag | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| shadcn-ui | shadcn/ui | https://github.com/shadcn-ui/ui | reference | reference-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| axe-core | axe-core | https://github.com/dequelabs/axe-core | adapter | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| playwright | Playwright | https://github.com/microsoft/playwright | adapter | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| storybook | Storybook | https://github.com/storybookjs/storybook | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| lighthouse | Lighthouse | https://github.com/GoogleChrome/lighthouse | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| backstopjs | BackstopJS | https://github.com/garris/BackstopJS | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| chromatic | Chromatic accessibility/visual workflow | https://www.chromatic.com/docs/ | reference | reference-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| w3c-clreq | Chinese Layout Requirements | https://www.w3.org/TR/clreq/ | derive | adopt-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| w3c-jlreq | Requirements for Japanese Text Layout | https://www.w3.org/TR/jlreq/ | derive | adopt-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| unicode-cldr | Unicode CLDR | https://github.com/unicode-org/cldr | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| fontsource | Fontsource | https://github.com/fontsource/fontsource | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| google-fonts | Google Fonts repository | https://github.com/google/fonts | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| fonttools | fontTools | https://github.com/fonttools/fonttools | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| harfbuzz | HarfBuzz | https://github.com/harfbuzz/harfbuzz | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| lucide | Lucide Icons | https://github.com/lucide-icons/lucide | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| phosphor | Phosphor Icons | https://github.com/phosphor-icons/core | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| tabler-icons | Tabler Icons | https://github.com/tabler/tabler-icons | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| octicons | GitHub Octicons | https://github.com/primer/octicons | adapter | reference-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| openmoji | OpenMoji | https://github.com/hfg-gmuend/openmoji | adapter | review-required | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| d3 | D3 | https://github.com/d3/d3 | adapter | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| vega-lite | Vega-Lite | https://github.com/vega/vega-lite | adapter | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| echarts | Apache ECharts | https://github.com/apache/echarts | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| observable-plot | Observable Plot | https://github.com/observablehq/plot | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| mermaid | Mermaid | https://github.com/mermaid-js/mermaid | adapter | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| graphviz | Graphviz | https://gitlab.com/graphviz/graphviz | adapter | adapter-next | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| svgo | SVGO | https://github.com/svg/svgo | adapter | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| vtracer | VTracer | https://github.com/visioncortex/vtracer | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| imagemagick | ImageMagick | https://github.com/ImageMagick/ImageMagick | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| sharp | sharp | https://github.com/lovell/sharp | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| c2pa | C2PA Content Credentials | https://spec.c2pa.org/ | adapter | adapter-next | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| ghent-workgroup | Ghent Workgroup Specifications | https://gwg.org/technical-specifications/ | derive | adopt-now | author; license; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| pdf-association | PDF Association standards map | https://pdfa.org/pdf-standards/ | reference | reference-now | author; license; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| adobe-print-ready | Adobe print-ready PDF guidance | https://helpx.adobe.com/indesign/desktop/print/print-production-and-file-creation/produce-print-ready-pdf-files.html | derive | reference-now | author; license; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| dielinelab | DielineLab | https://dielinelab.com/ | reference | review-required | author; license; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| diecutstudio | Die Cut Studio | https://www.diecutstudio.com/ | reference | reference-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| gs1 | GS1 General Specifications | https://www.gs1.org/standards/barcodes-epcrfid-id-keys/gs1-general-specifications | reference | reference-now | author; license; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| pptxgenjs | PptxGenJS | https://github.com/gitbrent/PptxGenJS | adapter | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| python-pptx | python-pptx | https://github.com/scanny/python-pptx | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| revealjs | reveal.js | https://github.com/hakimel/reveal.js | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| slidev | Slidev | https://github.com/slidevjs/slidev | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| typst | Typst | https://github.com/typst/typst | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| pagedjs | Paged.js | https://github.com/pagedjs/pagedjs | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| pdfbox | Apache PDFBox | https://github.com/apache/pdfbox | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| qpdf | QPDF | https://github.com/qpdf/qpdf | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| ghostscript | Ghostscript | https://git.ghostscript.com/?p=ghostpdl.git | adapter | review-required | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| verapdf | veraPDF | https://github.com/veraPDF/veraPDF-library | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| lottie-spec | Lottie Animation Format | https://github.com/lottie-animation-community/docs | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| lottie-web | lottie-web | https://github.com/airbnb/lottie-web | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| motion-one | Motion | https://github.com/motiondivision/motionone | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| framer-motion | Motion for React | https://github.com/motiondivision/motion | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| prefers-reduced-motion | WCAG reduced motion techniques | https://www.w3.org/WAI/WCAG22/Techniques/css/C39 | derive | adopt-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| gltf | glTF 2.0 | https://github.com/KhronosGroup/glTF | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| openpbr | OpenPBR Surface | https://github.com/AcademySoftwareFoundation/OpenPBR | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| materialx | MaterialX | https://github.com/AcademySoftwareFoundation/MaterialX | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| openusd | OpenUSD | https://github.com/PixarAnimationStudios/OpenUSD | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| opencolorio | OpenColorIO | https://github.com/AcademySoftwareFoundation/OpenColorIO | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| littlecms | Little CMS | https://github.com/mm2/Little-CMS | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| threejs | three.js | https://github.com/mrdoob/three.js | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| blender | Blender | https://projects.blender.org/blender/blender | adapter | review-required | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| freecad | FreeCAD | https://github.com/FreeCAD/FreeCAD | adapter | review-required | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| speckle | Speckle | https://github.com/specklesystems/speckle-server | adapter | review-required | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| spdx | SPDX Specification | https://github.com/spdx/spdx-spec | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| reuse | REUSE Specification | https://reuse.software/spec/ | derive | adopt-now | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| cyclonedx | CycloneDX | https://github.com/CycloneDX/specification | vendor-adapt | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| openssf-scorecard | OpenSSF Scorecard | https://github.com/ossf/scorecard | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| osv-scanner | OSV-Scanner | https://github.com/google/osv-scanner | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| slsa | SLSA | https://slsa.dev/spec/ | derive | adapter-next | author; allowedUsage; acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| sigstore | Sigstore | https://github.com/sigstore | adapter | review-required | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| hallmark-skill | Hallmark (anti-AI-slop design skill) | https://github.com/Nutlope/hallmark | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| taste-skill | Taste-Skill (anti-slop frontend) | https://github.com/Leonxlnx/taste-skill | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| huashu-design-skill | Huashu-Design（花叔Design，中文） | https://github.com/alchaincyf/huashu-design | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| uiux-pro-max-data | UI/UX Pro Max (design intelligence data) | https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| garden-skills | Garden Skills (ConardLi) | https://github.com/ConardLi/garden-skills | quarantine | review-required | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| motion-design-skill | Motion Design Skill (LottieFiles) | https://github.com/LottieFiles/motion-design-skill | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| design-motion-principles | Design Motion Principles | https://github.com/kylezantos/design-motion-principles | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| shipit-ui-design | ShipIt UI Design (11 skills) | https://github.com/shipiit/shipit-ui-design | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| terrazzo-dtcg | Terrazzo (DTCG tokens compiler) | https://github.com/terrazzoapp/terrazzo | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| front-end-design-checklist | Front-End Design Checklist | https://github.com/thedaviddias/Front-End-Design-Checklist | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| brand-resources-links | Brand Resources (links collection) | https://github.com/sturobson/brand-resources | reference | reference-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| style-dictionary-utils | Style Dictionary Utils | https://github.com/lukasoppermann/style-dictionary-utils | adapter | adapter-next | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse; reviewedBy; reviewedAt |
| game-ui-mobile-skill | game-ui-mobile-friendly-design-agent-skill | https://github.com/dungnotnull/game-ui-mobile-friendly-design-agent-skill | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| blender-3d-skill | blender (3D design via MCP) | https://github.com/jithinolickal/blender | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| motion-engine-skill | ai-ui-ux-motion-engine (Opace) | https://github.com/OpaceDigitalAgency/skills | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| brand-systems-skill | evidence-based-brand-systems | https://github.com/arome3/evidence-based-brand-systems | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| brand-identity-skill | brand-visual-identity | https://github.com/SkillMedev/brand-visual-identity | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| ai-graphic-design-skill | ai-graphic-design-skill | https://github.com/designrique/ai-graphic-design-skill | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| design-system-prompt | claude-design-system-prompt (Trystan-SA) | https://github.com/Trystan-SA/claude-design-system-prompt | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| claude2figma | claude2figma | https://github.com/senlindesign/claude2figma | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| extract-design-system | extract-design-system | https://github.com/arvindrk/extract-design-system | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| anydesign | anydesign (uxKero) | https://github.com/uxKero/anydesign | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| ppt-agent-skill | ppt-agent-skill (Akxan) | https://github.com/Akxan/ppt-agent-skill | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| swiftui-design-skill | swiftui-design-skill | https://github.com/Wholiver/swiftui-design-skill | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| claude-dolphin | claude-dolphin | https://github.com/nyldn/claude-dolphin | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| ux-audit-skill | ux-audit-skill (EliaAlberti) | https://github.com/EliaAlberti/ux-audit-skill | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| claude-design-skill-jiji | claude-design-skill (jiji262) | https://github.com/jiji262/claude-design-skill | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| brandbook-skill | brandbook-skill | https://github.com/echowang97/brandbook-skill | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| logo-designer-skill | logo-designer-skill (neonwatty) | https://github.com/neonwatty/logo-designer-skill | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| ecommerce-ai-skills | ecommerce-ai-skills (kangise) | https://github.com/kangise/ecommerce-ai-skills | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| screenshot-to-design-system | screenshot-to-design-system | https://github.com/WCF900905/screenshot-to-design-system | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| motion-forensics | ui-clone-skills (voidmatcha) | https://github.com/voidmatcha/ui-clone-skills | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| springy-motion | springy-motion | https://github.com/OtherdaysStudio/springy-motion | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| design-thinking-facilitation | kopfwelt skills | https://github.com/kopfwelt/skills | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| web-content-designer | web-content-designer | https://github.com/lowtidebuild/web-content-designer | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| genjutsu | genjutsu (AThevon) | https://github.com/AThevon/genjutsu | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| game-creative-skills | GameCreative-skills | https://github.com/wotonger/GameCreative-skills | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| ai-product-os | AI-Product-OS | https://github.com/Nihalgraphics/AI-Product-OS-for-UI-UX-Brand-Prototype | quarantine | review-required | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| baoyu-design | baoyu-design (JimLiu) | https://github.com/JimLiu/baoyu-design | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| design-md-skill | design-md-skill (arumwu) | https://github.com/arumwu/design-md-skill | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| document-design-system | document-design-system (Avinava) | https://github.com/Avinava/document-design-system | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| dataviz-critique-skills | dataviz-critique-skills | https://github.com/zhanyi789/dataviz-critique-skills | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| brand-identity-generator | brand-identity-generator | https://github.com/AbdulkareemKR/brand-identity-generator | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| ultimate-uiux-design-skills | ultimate.UIUX.design.skills | https://github.com/ca-who-codes/ultimate.UIUX.design.skills | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| ux-writing-skill | ux-writing-skill (content-designer) | https://github.com/content-designer/ux-writing-skill | reference | reference-now | author; license; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| hue | design-lab/knowledge/visual-quality/hue | https://github.com/dominikmartn/hue | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| qiaomu-design | design-lab/knowledge/visual-quality/qiaomu-design | https://github.com/joeseesun/qiaomu-design | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| interface-design | design-lab/knowledge/visual-quality/interface-design | https://github.com/Dammyjay93/interface-design | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| visual-note-card | design-lab/knowledge/visual-quality/visual-note-card | https://github.com/beilunyang/visual-note-card-skills | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |
| affiliate-skills | design-lab/knowledge/visual-quality/affiliate-skills | https://github.com/Affitor/affiliate-skills | vendor-adapt | adopt-now | author; allowedUsage; version(40-hex-git-sha); acquiredAt; contentHash(sha256); redistributable; modelInputAllowed; commercialUse |

