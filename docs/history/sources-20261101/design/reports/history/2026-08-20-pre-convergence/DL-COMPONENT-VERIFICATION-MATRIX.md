# DL 组件在线核实矩阵（2026-08-17，30 项，web_search 逐项核实）

> 核实对象：外部调研报告列举的全部技术组件。方法：3 组并行 web_search（来源=GitHub/HF/ModelScope/官方博客）。
> 用途：把报告主张落地为可执行判断（适配器候选/源码吸收/排除/边界冲突），更新后续任务清单。

## 一、视觉理解与视觉专项（8 项）

| 组件 | 许可证 | 维护 | 适配判断 | 风险 |
|---|---|---|---|---|
| CLIP（OpenAI） | MIT | 官方停滞；OpenCLIP 活跃 | **适配器候选**：视觉编码 provider 首选（encode_image/text 接口极简） | 低 |
| SigLIP（Google） | Apache-2.0 | 活跃（SigLIP-2 2025） | **适配器候选**：CLIP 替代，同一能力契约 | 低 |
| BLIP-2（Salesforce） | 代码 BSD-3；权重不统一 | 停更 | 源码吸收候选（Q-Former 参考）；provider 需逐权重核实 | **中** |
| Florence-2（Microsoft） | MIT | HF/社区活跃 | **适配器候选（最友好）**：0.23/0.77B 轻量多任务（字幕/检测/分割/OCR 一模型） | 低 |
| InternVL（上海AI Lab） | 代码 MIT；权重逐 checkpoint 混乱 | 非常活跃 | 适配器候选（VLM）；只契约化小规格 | **中** |
| SAM（Meta） | Apache-2.0 | 停更（重心 SAM2） | 源码吸收候选（promptable 分割参考实现） | 低 |
| SAM 2（Meta） | Apache-2.0 | 活跃（2.1） | **适配器候选**：图像+视频统一分割首选 | 低 |
| Grounding DINO（IDEA） | Apache-2.0 | 放缓（1.5/2.0 后续） | **适配器候选**：开放词汇检测，与 SAM2 互补 | 低 |

## 二、OCR / 文档 / 布局 / 美学评估（7 项）

| 组件 | 许可证 | 维护 | 适配判断 | 风险 |
|---|---|---|---|---|
| PaddleOCR（百度） | Apache-2.0 | 活跃 v3.x | **适配器首选**：OCR+版面，本地成熟（AGPL 依赖隔离） | 低 |
| LayoutParser | Apache-2.0 | 2021 停更 | 仅引擎抽象参考 | 低 |
| DocFormer（微软） | — | 无官方代码 | **排除** | — |
| LayoutLM v1/v2 | 代码 MIT/权重 MIT | 稳定 | 可用（字段抽取）；**v3 权重 cc-by-nc-sa 非商用，避开** | 低（v3 除外） |
| LayoutDiffusion | [未核实] | 单作者研究代码 | **排除**（许可不明、方向相反） | — |
| NIMA（idealo 实现） | Apache-2.0 | 稳定 | 美学打分验证器候选，本地可跑 | 低 |
| LAION aesthetics（官方） | MIT | 活跃 | **美学打分 adapter 首选** | 低 |

## 三、基础设施 / 设计软件 / 协议（15 项）

| 组件 | 许可证 | 边界分类 | 判断 |
|---|---|---|---|
| LangGraph / AutoGen(AG2→MS Agent Framework) / CrewAI | MIT | **违反边界**（通用 Agent 运行时） | 不依赖，仅借鉴概念 |
| Neo4j | Community GPLv3 / Enterprise 商业 | **违反边界**（通用知识治理/图存储） | 不依赖 |
| GraphRAG（微软） | MIT | **违反边界**（图存储） | 不依赖 |
| Apache AGE | Apache-2.0 | **违反边界**（图存储） | 不依赖 |
| Qdrant / Ollama / vLLM | Apache-2.0 / MIT / Apache-2.0 | 重运行时 | **仅外部服务适配**（标准 API，不内置） |
| **MCP** | MIT（已捐 Linux Foundation） | **协议标准，非运行时** | **可适配首选**：项目与外部 Agent 生态互操作的 adapter 层 |
| OpenAssetIO | Apache-2.0（ASWF） | 标准 | 可适配（媒体资产互操作，领域需评估） |
| Tauri | MIT/Apache-2.0 | 桌面壳层 | 可适配（视项目形态；当前无桌面产品线） |
| Penpot | MPL-2.0 | 同类产品 | 仅参考（插件/格式互操作） |
| Inkscape | GPL-2.0+ | 格式互操作 | 仅参考（SVG/矢量） |

## 四、核实结论 → 任务更新

### 可落地为 provider/adapter 候选（E0 登记，真实接入需 E2/E3 运行时取证）

1. **视觉编码**：CLIP / SigLIP（同一 capability 契约 `vision.encoding`，Florence-2 亦可覆盖）
2. **分割/检测**：SAM 2（`image.segment`）+ Grounding DINO（`image.detect.open_vocab`）
3. **OCR/版面**：PaddleOCR（`document.ocr` / `document.layout`）
4. **美学评估**：LAION aesthetics + NIMA 双验证器（`quality.aesthetic_score`）
5. **互操作协议**：MCP（adapter 协议层首选）；OpenAssetIO（资产互操作，评估）

### 源码吸收候选（算法参考，非仓库目标）

- BLIP-2 Q-Former 结构、SAM promptable 分割参考实现（宽松许可；吸收走 external_asset_intake 管线）

### 明确排除

- DocFormer（无官方代码）、LayoutDiffusion（许可不明/方向相反）、LayoutParser（停更，仅参考）
- LayoutLM v3 权重（非商用）、BLIP-2/InternVL 部分权重（逐 checkpoint 核实）

### 边界冲突（不依赖）

- Agent 运行时：LangGraph / AutoGen / CrewAI；图存储：Neo4j / GraphRAG / AGE
- 重运行时仅外部适配：Qdrant / Ollama / vLLM（标准 API 从外部调用）

## 五、来源

openai/CLIP、mlfoundations/open_clip、google-research/big_vision、salesforce/LAVIS、HF microsoft/Florence-2、OpenGVLab/InternVL、facebookresearch/segment-anything、facebookresearch/sam2、IDEA-Research/GroundingDINO、PaddleOCR 官方、LAION-AI/aesthetic-predictor、langchain-ai/langgraph、microsoft/autogen、crewAIInc/crewAI、neo4j.com（open-core）、microsoft/graphrag、apache/age、qdrant/qdrant、OpenAssetIO/OpenAssetIO、ollama、vllm-project/vllm、tauri-apps/tauri、penpot/penpot、Inkscape/inkscape、anthropic.com（MCP 捐赠公告）、wikipedia.org/wiki/Ollama
