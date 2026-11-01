# DESIGN-LAB 项目完整汇总（所有内容）

> 设计能力所有者：648设计技能库/边界契约v4.2/设计能力IGNORE

## 一、项目配置

### AGENTS.md

# AGENTS.md - DESIGN-LAB 设计实验室 Operating Guide

> 全局执行标准（跨软件跨项目）：见 WORK-LAB `00-governance/global-execution-standard.md`
> （执行生命周期：理解→扫技能→分片→执行→验证→落地；全局边界：E盘禁访/数据不外溢/官方优先/全功率/审计分层）。
> 经验教训铁律（核实优先/治理最小化/官方优先）：见本项目 `LESSONS_LEARNED.md`。

## 项目定位

- DESIGN-LAB 拥有设计能力（models/tools/generation params/assets/specs/quality gates）
- 设计能力不被 WORK-LAB 采集或管理（IGNORE），由本项目独立负责

## 执行规范

- 执行任务前先扫描匹配 SKILL（见全局执行标准步骤②）
- 设计产物留在本项目内，不外溢到其他项目/共享库
- 更新以官方发布为准，不私自打包

## 模块

- design-lab/：设计核心
- design-system/：设计系统
- minigame-runtime/：小游戏运行时
- evals/：评估

（项目特有规则在此基础上补充）

---

## 二、DSH 会话详细内容
### 会话 04149d33-5525-49e1-affd-8e09b66355a2 (创建 1787157947803)

**你说:**
- [1] 用 web_search 搜索【开源设计软件已验证自动化脚本】：①Blender Python 脚本集合（bpy 批处理：建模/渲染/导出脚本）②GIMP script-fu/Python-fu 脚本集合 ③Figma 插件/脚本模板（自动化操作模板）④Penpot 脚本/自动化。对每个：核实仓库/许可证/脚本功能/维护/能否转化纳入。输出 markdown 表格。重点是可直接下载的脚本文件。真实搜索，不臆造。

**我执行的工具:** run_code

**我的结论:** 

---

### 会话 3fa1b0ab-d6b5-4960-86e3-10f6443549da (创建 1787067601108)

**你说:**
- [1] 用 web_search 全面调研【设计资产与设计系统管理的开源工具】：数字资产管理 DAM（如 ResourceSpace、Razuna、Piwigo）、设计 token 管理（Style Dictionary、Tokens Studio、terrazzo）、design system 管理与文档（Storybook、Design Tokens WG 实现）、品牌资产库管理、字体管理（FontBase 等开源替代）、配色管理、设计版本管理。对每个核实：①真实仓库与开发者 ②许可证 ③能力 ④维护状态 ⑤对本项目（DESIGN-LAB）适配判断：可吸收源码/做 adapter/仅参考。输出 markdown 表格。真实搜索，不臆造，搜不到标[未核实]。

**我执行的工具:** web_search, run_code, report

**我的结论:** 

---

### 会话 618d8b1c-b86b-4ad6-9d67-563333ef4b2b (创建 1787067601078)

**你说:**
- [1] 用 web_search 全面调研【操作设计软件的开源库/脚本生态】：Photoshop/Illustrator 的 UXP/ExtendScript 自动化库、Figma API 与插件生态（如 figma-js、Figma REST API 封装）、Blender Python API 相关库、Inkscape CLI 与 Python 封装（cairosvg/svglib）、GIMP 脚本、SVG 处理库（svgo、resvg、sharp）、PDF 设计操作库（pypdf、reportlab）、图像处理库（Pillow/OpenCV/ImageMagick）。对每个项目用 web_search 核实：①真实仓库与开发者 ②许可证 ③主要能力（如何操作对应设计软件/格式）④维护状态 ⑤对本项目（DESIGN-LAB：契约/验证器驱动、平台中立、验证器仅标准库、可 vendored 源码

**我执行的工具:** run_code

**我的结论:** 

---

### 会话 8cc0a4d5-2a45-4c76-b20b-cfb56405c745 (创建 1786978592444)

**你说:**
- [1] 核实这些基础设施与设计软件组件：LangGraph、AutoGen、CrewAI、Neo4j、GraphRAG、Apache AGE、Qdrant、OpenAssetIO、Ollama、vLLM、Tauri、Penpot、Inkscape、MCP(Model Context Protocol)。对每个用 web_search 核实：①真实存在性与开发者 ②许可证 ③主要用途 ④维护状态 ⑤与 DESIGN-LAB 的边界关系：这些是否属于'通用 Agent 运行时/通用知识治理/重运行时'（项目边界明确不做），或可作为 adapter/参考。输出 markdown 表格，列：组件|开发者|许可证|用途|维护状态|与项目边界关系(违反边界/仅参考/可适配)+原因。基于真实搜索结果，不要臆造；搜不到的标注[未核实]。

**我执行的工具:** web_search, run_code, report

**我的结论:** 

---

### 会话 8ee9d2bc-8f4d-4fe9-8586-2a578d56078c (创建 1787156566414)

**你说:**
- [1] 用 web_search 调研【增强设计软件操作能力的开源项目】（重点）：①Photoshop/Illustrator 自动化开源（ExtendScript 库、UXP 模板、psd-tools(Python)、ag-psd(JS)、psd.js） ②Figma 自动化开源（figma-js、@figma/rest-api-spec、figma tokens 同步工具） ③Inkscape/Blender/GIMP CLI 自动化封装 ④设计文件解析库（psd-tools/ag-psd/SVG/PDF 操作） ⑤MCP design servers（Photoshop MCP、Figma MCP、design tools MCP 生态） ⑥设计自动化框架（批量导出、design tokens 管线、视觉回归）。对每个核实：仓库/许可证/能力/维护/能否直接增强本项目操作能力（吸收源码/做 

**我执行的工具:** run_code

**我的结论:** 

---

### 会话 afd2e93d-92f4-41a4-8e61-0dd4edc40d24 (创建 1787157947707)

**你说:**
- [1] 用 web_search 搜索【Adobe 系 + 矢量软件已验证自动化脚本库/集合】：①Photoshop ExtendScript/JSX 脚本集合（github 上 star 较高的脚本库，如批量导出/图层处理/滤镜/切图工具）②Illustrator JSX/ExtendScript 脚本集合（画板/导出/路径/文字处理）③Inkscape CLI 脚本/批处理模板。对每个找到的脚本库/仓库：核实仓库/许可证/主要脚本功能/维护状态/能否直接转化纳入（下载脚本本体 + 加 SPDX 头 + 归档）。输出 markdown 表格：仓库|许可证|脚本功能|维护|转化建议。重点是**可直接下载的脚本文件/集合**（不是框架）。真实搜索，不臆造。

**我执行的工具:** run_code, report

**我的结论:** 

---

### 会话 bdb993e4-da5a-4d8b-baef-b474a3c66e2e (创建 1787156566383)

**你说:**
- [1] 用 web_search + 本地调研【DESIGN-LAB 的同源/前身项目】：①OPEN-DESIGN-Assistance（本项目的迁移源/前身，已归档）的历史与迁移链 ②GitHub 上同名或高度相似的 design-lab / design-labs / ai-design-lab 开源项目（如 design-lab 教学项目、designlab 教育、open-source design lab） ③与 DESIGN-LAB 定位相近的设计能力/生产基础设施项目。对每个核实：仓库/许可证/能力/与本项目关系（同源/同名/相近）/可借鉴点。输出 markdown 表格。真实搜索+本地文件核实，不臆造。

**我执行的工具:** run_code, web_search

**我的结论:** 

---

### 会话 c1cfa2c3-e2af-4963-9ed9-f3ce48794ef5 (创建 1786978592412)

**你说:**
- [1] 核实这些开源组件（视觉理解与视觉专项）：CLIP、SigLIP、BLIP-2、Florence-2、InternVL、SAM、SAM2、Grounding DINO。对每个组件用 web_search 核实：①真实存在性与开发者 ②许可证（MIT/Apache/BSD/GPL等） ③主要能力与是否可本地部署 ④当前维护状态（活跃/停滞） ⑤作为 DESIGN-LAB（一个契约/验证器驱动、平台中立、不做重运行时的设计能力仓库）的 adapter/provider 候选是否合适。输出 markdown 表格，每行一个组件，列：组件|开发者|许可证|能力|维护状态|适配判断(适配器候选/源码吸收候选/不适合+原因)|许可证风险。基于真实搜索结果，不要臆造；搜不到的标注[未核实]。

**我执行的工具:** run_code

**我的结论:** 

---

### 会话 d60508d5-7e15-4d0e-8b14-bac1e2421bc8 (创建 1787156566350)

**你说:**
- [1] 用 web_search 调研【AI 设计类同行/同类项目与产品】（2024-2026）：Agentic design 系统、AI 设计助手、design automation 平台、design intelligence 产品（如 v0/Vercel、galileo、Recraft、Khroma、uizard、Lovable 设计侧、Canva AI、Adobe Firefly 工作流、Figma AI、Dora、Webflow AI、Relume、Framer AI、以及开源 agentic design 项目如 design-systems agents、UI generation agents、MCP design servers）。对每个核实：①真实产品/项目与公司 ②许可证（开源则标，商业则标商业） ③核心能力（尤其设计软件操作/生成/评审能力） ④与本项目（DESIGN-LA

**我执行的工具:** run_code

**我的结论:** 

---

### 会话 dfc6ce7f-4b75-4061-9047-93cc748d9cc4 (创建 1786978592426)

**你说:**
- [1] 核实这些开源组件（OCR/文档理解/布局/美学评估）：PaddleOCR、LayoutParser、DocFormer、LayoutLM、LayoutDiffusion、NIMA、LAION aesthetics(审美打分)。对每个组件用 web_search 核实：①真实存在性与开发者 ②许可证 ③主要能力与本地部署可行性 ④维护状态 ⑤作为 DESIGN-LAB（契约/验证器驱动、平台中立、不做重运行时的设计能力仓库）的 adapter/provider 候选是否合适。输出 markdown 表格，列：组件|开发者|许可证|能力|维护状态|适配判断|许可证风险。基于真实搜索结果，不要臆造；搜不到的标注[未核实]。

**我执行的工具:** run_code

**我的结论:** 

---

### 会话 e1792d7c-e4d5-422f-a697-a2c43eff8d53 (创建 1787157947884)

**你说:**
- [1] 用 web_search 搜索【生成与自动化工具脚本】：①ComfyUI workflow JSON 模板（已验证可用的设计/图像生成 workflow）②ffmpeg 批处理脚本集合（转码/抽帧/合成模板）③SVG 工具脚本（svgo/resvg/rsvg 批处理）④Style Dictionary token 构建脚本模板。对每个：核实仓库/许可证/功能/能否转化纳入。输出 markdown 表格。重点是可直接下载的脚本/workflow 文件。真实搜索，不臆造。

**我执行的工具:** run_code

**我的结论:** 

---

### 会话 e2606ffe-2484-41b5-a47f-829b41abafbe (创建 1787067601132)

**你说:**
- [1] 用 web_search 全面调研【开源设计软件本体与设计自动化管线】：矢量/位图/UI 设计软件（Penpot、Inkscape、GIMP、Krita、Pencil2D、Synfig、Gravit 类）、设计交付自动化（Chromatic、设计 token 同步、批量导出管线）、印刷/PDF 自动化（PDF/X 校验工具如 veraPDF）、设计 CI 思路（视觉回归如 Playwright Screenshot 对比、Percy 替代开源如 backstopjs）。对每个核实：①真实仓库与开发者 ②许可证 ③能力 ④维护状态 ⑤对本项目（DESIGN-LAB）适配判断：可吸收源码/做 adapter/仅参考。输出 markdown 表格。真实搜索，不臆造，搜不到标[未核实]。

**我执行的工具:** web_search, run_code

**我的结论:** 

---

### 会话 session-0006728b-5e47-49d2-98cb-fea0d9803c2c (创建 1786808268241)

**你说:**
- [1] 载入项目定位，查看交接摘要等内容，交接文档已完成

文件：reports/V42_HANDOFF_SUMMARY_20260816.md（4.2KB，精炼自包含）



commit：b9f69ac，已 push，本地 == 云端 == b9f69acd13f5...，工作树干净。



文档结构（专为 DSH 接手设计）

段	内容

状态	✅ DUAL-END SYNC（HEAD/云端 SHA + 工作树干净）

本轮 4 项工作	H3 迁移（39.55GB）、外部资产索引+verifier、目录边界固化、MINIGAME 清理

验证链	300/300、索引 PASS、零模型权重、diff-check 干净

Release Gate	诚实 BLOCKED findings=7（本轮不改就绪度）

给 HARNESS 速查	外置库路径 + 指向关系（extra_model_paths
- [2] 先查看SKILL里面的内容规划 和 配置是不是HARNESS 需要的，如果不需要就不用了
- [3] background job pwsh-6 (pwsh: python 'D:/All projects/DESIGN-LAB/design-lab/scripts/verify_design_lab.py') finished [status: completed, exit code: 1]. Read its output with job_output.
- [4] background job pwsh-16 (pwsh: $env:TMP = 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/tmp'; $env:TEMP = 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/tmp'; python scripts/run_python_tests.py 2>&1 | Select-Object -Last 40) finished [status: completed, exit code: 1]. Read its output with job_output.
- [5] background job pwsh-19 (pwsh: python 'D:/All projects/DESIGN-LAB/design-lab/scripts/verify_design_lab.py' 2>&1 | Select-Object -Last 22) finished [status: completed, exit code: 1]. Read its output with job_output.
- [6] background job pwsh-21 (pwsh: python 'D:/All projects/DESIGN-LAB/design-lab/scripts/verify_design_lab.py' 2>&1 | Select-Object -Last 25) finished [status: completed, exit code: 1]. Read its output with job_output.
- [7] background job pwsh-23 (pwsh: $env:TMP = 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/tmp'; $env:TEMP = 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/tmp'; python -m unittest design-lab.tests.test_open_design_host_adapter_neutrality design-lab.tests.test_oda4_0302_manifest_compat.OpenDesignHostAdapterNeutralityTests design-lab.tests.test_verifier_internals.OpenDesignAssistanceTests 2>&1 | S
- [8] background job pwsh-22 (pwsh: python 'D:/All projects/DESIGN-LAB/design-lab/scripts/verify_design_lab.py' 2>&1 | Select-Object -Last 25) finished [status: completed, exit code: 1]. Read its output with job_output.
- [9] background job pwsh-24 (pwsh: $env:TMP = 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/tmp'; $env:TEMP = 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/tmp'; python scripts/run_python_tests.py 2>&1 | Select-String -Pattern '^(ERROR|FAIL):|^Ran |^FAILED|^OK' | ForEach-Object { $_.Line }) finished [status: completed, exit code: 1]. Read its output with job_output.
- [10] background job pwsh-27 (pwsh: cd 'D:/All projects/DESIGN-LAB/minigame-runtime'; node build.js android; node scripts/prepare-android-webview.mjs) finished [status: completed, exit code: 0]. Read its output with job_output.
- [11] background job pwsh-28 (pwsh: cd 'D:/All projects/DESIGN-LAB/minigame-runtime'; node scripts/run-tests.cjs 2>&1 | Select-Object -Last 20) finished [status: completed, exit code: 1]. Read its output with job_output.
- [12] background job pwsh-29 (pwsh: cd 'D:/All projects/DESIGN-LAB/minigame-runtime'; node scripts/run-tests.cjs) finished [status: completed, exit code: 0]. Read its output with job_output.
- [13] background job pwsh-30 (pwsh: cd 'D:/All projects/DESIGN-LAB/minigame-runtime'; cmd /c 'node scripts/run-tests.cjs > r4-testout.txt 2>&1'; 'EXIT=' + $LASTEXITCODE) finished [status: completed, exit code: 0]. Read its output with job_output.
- [14] background job pwsh-31 (pwsh: cd 'D:/All projects/DESIGN-LAB/minigame-runtime'; cmd /c 'node --test --test-concurrency=1 tests\*.test.js > r4-testout2.txt 2>&1'; 'EXIT=' + $LASTEXITCODE) finished [status: completed, exit code: 0]. Read its output with job_output.
- [15] background job pwsh-35 (pwsh: cd 'D:/All projects/DESIGN-LAB/minigame-runtime'; $files = @('state.test','miniGameRuntime.test','analyticsIntegration.test','feedback.test','firstRunExperience.test','platform.test','canvasRenderer.test','uiLabels.test','skins.test','rewardGuard.test','game.test','rollback.test'); $tp=0; $tf=0; $tt=0; foreach ($f in $files) {;   if (-not (Test-Path ('tests\\' + $f + 
- [16] background job pwsh-34 (pwsh: cd 'D:/All projects/DESIGN-LAB/minigame-runtime'; node build.js wechat; node build.js douyin; node build.js android; node scripts/prepare-android-webview.mjs; 'REBUILD_DONE') finished [status: completed, exit code: 0]. Read its output with job_output.
- [17] background job pwsh-38 (pwsh: cd 'D:/All projects/DESIGN-LAB/minigame-runtime'; $files = @('state.test','actions.test','feedback.test','canvasRenderer.test','miniGameRuntime.test','analyticsIntegration.test','game.test','uiLabels.test','skins.test','rewardGuard.test','firstRunExperience.test','platform.test','eventChain.test','events.test','visualState.test','skinAuthoring.test'); $tp=0; $tf=0; $t
- [18] background job pwsh-39 (pwsh: cd 'D:/All projects/DESIGN-LAB/minigame-runtime'; $tp=0; $tf=0; $tt=0; $failedFiles = @(); Get-ChildItem 'tests/*.test.js' | ForEach-Object {;   $out = 'r4full-' + $_.BaseName + '.txt';   cmd /c ('node tests\\' + $_.Name + ' > ' + $out + ' 2>&1') | Out-Null;   $last = Get-Content $out | Select-Object -Last 8;   $p = 0; $fl = 0;   foreach ($ln in $last) { if ($ln -matc
- [19] 把COMFY UI 和 H3模型 给我配置部署上，桌面显示COMFY UI
- [20] 卡哪了 为什么进程停止了？
- [21] background job pwsh-3 (pwsh: cmd /c 'cd /d "D:\All projects\Design External Configuration\toolchains\comfyui\ComfyUI_windows_portable" && .\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --port 8188 --disable-auto-launch && --output-directory "D:/All projects/DESIGN-LAB/.hermes/task-runtime/comfyui\output" && --temp-directory "D:/All projects/DESIGN-LAB/.hermes/task-runtim
- [22] background job pwsh-4 (pwsh: cmd /c '"D:\All projects\Design External Configuration\toolchains\comfyui\ComfyUI_windows_portable\python_embeded\python.exe" -s "D:\All projects\Design External Configuration\toolchains\comfyui\ComfyUI_windows_portable\ComfyUI\main.py" --windows-standalone-build --port 8188 --disable-auto-launch --output-directory "D:/All projects/DESIGN-LAB/.hermes/task-runtime/comfy
- [23] background job pwsh-5 (pwsh: cmd /c '"D:\All projects\Design External Configuration\toolchains\comfyui\ComfyUI_windows_portable\python_embeded\python.exe" -s "D:\All projects\Design External Configuration\toolchains\comfyui\ComfyUI_windows_portable\ComfyUI\main.py" --windows-standalone-build --port 8188 --disable-auto-launch --output-directory "D:/All projects/DESIGN-LAB/.hermes/task-runtime/comfy
- [24] 继续
- [25] 我要的快捷方式呢？
- [26] You are repeating the exact same tool call with identical arguments. Carefully analyze the previous result before calling again: if the task is not complete, try a different approach or different arguments instead of repeating the call.
- [27] Repeated tool call detected:
- tool: pwsh
- consecutive_calls: 5
- arguments: {"command":"try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8188/system_stats' -UseBasicParsing -TimeoutSec 5; 'HTTP ' + $r.StatusCode } catch { 'NOT_READY' }","description":"Poll ComfyUI HTTP"}
The repeated calls are not making progress. Do not call this tool with these exact arguments again. Inspect the latest resu
- [28] Repeated tool call detected:
- tool: pwsh
- consecutive_calls: 8
- arguments: {"command":"try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8188/system_stats' -UseBasicParsing -TimeoutSec 5; 'HTTP ' + $r.StatusCode } catch { 'NOT_READY' }","description":"Poll ComfyUI HTTP"}
The repeated calls are not making progress. Do not call this tool with these exact arguments again. Inspect the latest resu
- [29] background job pwsh-2 (pwsh: cmd /c '"D:\All projects\Design External Configuration\toolchains\comfyui\ComfyUI_windows_portable\python_embeded\python.exe" -s "D:\All projects\Design External Configuration\toolchains\comfyui\ComfyUI_windows_portable\ComfyUI\main.py" --windows-standalone-build --port 8188 --disable-auto-launch --output-directory "D:/All projects/DESIGN-LAB/.hermes/task-runtime/comfy
- [30] 没有对应图标啊
- [31] 删掉两个没用的
- [32] http://127.0.0.1:8188/  我进入界面了  检查下是否可用
- [33] 开始测试
- [34] background job pwsh-5 (pwsh: python 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/comfyui/poll_h3.py') finished [status: completed, exit code: 1]. Read its output with job_output.
- [35] background job pwsh-7 (pwsh: python 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/comfyui/poll_h3_3.py') finished [status: completed, exit code: 1]. Read its output with job_output.
- [36] 还有什么任务，历史任务，任务包任务
- [37] 继续
- [38] 音频视频在哪  路径给我
- [39] 先这样
- [40] 其他任务呢
- [41] 项目总览和项目健康没了啊？跨项目运行状态直接最上面  其他没了？？？？？？
- [42] 上传双端一致
- [43] 2不要管了
- [44] 对
- [45] 什么意思？现在双端一致吗？
- [46] 合并
- [47] # DESIGN-LAB V2 云端项目全量架构审计、产品重规划与重构迁移任务包

## 执行摘要与审计基线

### 审计对象与证据强度

本次审计针对云端私有仓库 **`DTALEX66/DESIGN-LAB`**。通过已连接的 GitHub 仓库直接读取，确认该仓库真实存在，默认分支为 `main`，仓库描述为 **“AI-native open visual design laboratory / AI 原生开放视觉设计实验室”**；仓库创建于 **2026-03-18**，本次可见元数据中最近一次 push 为 **2026-04-13**。同时确认 `DTALEX66/OPEN-DESIGN-Assistance` 已归档，并明确迁移至 DESIGN-LAB；同一账号下还存在私有仓库 `WORK-LAB` 与 `ArcheAxis`。

本轮直接读取到的 DESIGN-LAB 
- [48] 调研下本项目结合发你的内容，结合任务包，结合蓝图，结合历史规划，到底本项目后续应该怎么做？
- [49] 已重新审计云端 DTALEX66/DESIGN-LAB。这里的 DESIG-LAB 按正式名称统一为 DESIGN-LAB / 设计实验室。

一、当前云端真实结论

当前 main 最新提交为 a60fc925，已加入 MiniMax H3 生产级视频、音频和 MP4 取证文件。

但当前主分支不是可交付状态：

最新 Canonical CI：失败
Python gate：失败
MiniGame gate：失败
Generated artifact gate：失败
当前不是 E4 发布状态
旧的 DL-R4-FINAL-AUDIT、PROJECT_STATUS、ROADMAP 仍引用旧分支和旧 SHA，不能作为当前真实状态

最新失败记录见：GitHub Actions Run 31951061243。

具体失败：

Android WebView 生成文件未同步
index.htm
- [50] The approval policy changed from "ask" to "never" (changed by the user).
- [51] background job pwsh-3 (pwsh: cd 'D:/All projects/DESIGN-LAB/minigame-runtime'; cmd /c 'node --test --test-concurrency=1 tests\*.test.js > p0-mg.txt 2>&1'; 'EXIT=' + $LASTEXITCODE; Get-Content p0-mg.txt | Select-Object -Last 6) finished [status: completed, exit code: 0]. Read its output with job_output.
- [52] 全部修复，全量执行后续任务，除去H3模型和COMFYUI任务，其他任务全部执行
- [53] This is an automatically generated checkpoint condensing an earlier span of the conversation to free up context. Treat the captured context as established background and build on it without restating it. Continue the task directly from the messages that follow, without acknowledging this checkpoint.

<compacted-summary>## Primary Request and Intent
- User (Chinese, project owner) provided R4 task 
- [54] 总结摘要上传，双端（云端仓库和本地仓库）一致
- [55] DESIGN‑LAB 调研报告完整总结
这份文档是一套完整的AI 原生职业设计操作系统 DESIGN‑LAB深度调研与从生态调研→技术架构→产品定义→落地规划的全链路研究文档，核心定位：不做 AI 绘图工具、不复刻 Figma/Adobe，而是打造设计智能中间层（Design Intelligence Platform），充当连接需求、AI 智能、专业设计软件、生产交付系统的开放操作层，填补全球现有工具缺失的 “设计工程中间抽象层” 空白。文档分为开源生态调研、战略收敛、核心协议定义、技术蓝图、V1.0 产品设计、落地规划多个阶段。
一、前期开源生态盘点（能力地图）
调研梳理了构建 AI 设计系统需要的全部开源组件，覆盖十几大技术领域：
AI 视觉理解基础层：CLIP、SigLIP、BLIP‑2、Florence‑2、InternVL，解决 AI “看懂设计”，用于案例检索、图像语义解析；
- [56] 回归到项目，回归到项目定位，收敛一下
- [57] 把发你的报告收敛到本项目，符合定位的后续任务，你根据这些文档先调研下，然后看看后续有什么任务
- [58] 有能直接吸收源码的吗？
- [59] 整理所有未完成的任务，包括对于调研你的分析后的任务，调整后给我完整的后续任务
- [60] 调研报告你是否先去网上一一对应分析了
- [61] Background subagent dfc6ce7f-4b75-4061-9047-93cc748d9cc4 reported:已核实 7 个开源组件（基于 web_search 真实结果，未核实项已标注）。结论：
- PaddleOCR（百度，Apache-2.0，活跃 v3.x）：首选 OCR+版面 adapter，本地部署成熟；注意 AGPL 依赖隔离。
- LayoutParser（Apache-2.0，2021 停更）：仅作版面引擎抽象参考，不推荐长期 provider。
- DocFormer（微软论文，官方代码[未核实]）：无官方实现、未入 transformers，排除。
- LayoutLM v1/v2（代码 MIT、权重 MIT）可用；v3 权重 cc-by-nc-sa-4.0 非商用，商用须避开。
- LayoutDiffusion（许可[未核实]、单作者研究代码
- [62] Background subagent dfc6ce7f-4b75-4061-9047-93cc748d9cc4 finished and will do no further work unless you send it more.Its closing message:已完成全部 7 个组件的逐项 web_search 核实，结果以上方 markdown 表格为准。关键要点：

- **真实存在性**：7 个组件全部真实存在（论文/仓库可查）；但 **DocFormer 官方代码未发布**（仅第三方实现）、**NIMA 官方代码未发布**（主流为 idealo 实现）。
- **许可证**：PaddleOCR Apache-2.0、LayoutParser Apache-2.0、LayoutLM 代码 MIT 但 **v3 权重非商用（cc-by-nc-sa-4.0）**、LAION
- [63] Background subagent 8cc0a4d5-2a45-4c76-b20b-cfb56405c745 reported:已完成 15 个组件的真实 web_search 核实（全部有来源，无"未核实"项），输出为 markdown 表格。

**违反边界（通用 Agent 运行时，不可依赖，仅可借鉴概念）**：LangGraph（MIT, LangChain Inc.）、AutoGen→AG2→Microsoft Agent Framework（MIT, Microsoft/社区）、CrewAI（MIT, CrewAI Inc.）。

**违反边界（通用知识治理/图存储）**：Neo4j（Community GPLv3/Enterprise 商业 open-core, Neo4j Inc.）、GraphRAG（MIT, Microsoft, 2025 仍发 v2.0/v2.1 
- [64] Background subagent 8cc0a4d5-2a45-4c76-b20b-cfb56405c745 finished and will do no further work unless you send it more.Its closing message:核实任务已完成。上面给出了完整的 15 组件 markdown 表格（含许可证、开发者、用途、维护状态、边界分类及原因），所有条目均来自真实搜索结果并附有来源链接，无"未核实"项。结果已通过 `report` 同步给上级代理。
- [65] Background subagent c1cfa2c3-e2af-4963-9ed9-f3ce48794ef5 finished and will do no further work unless you send it more.Its closing message:核实完毕。基于三轮 web_search 结果（来源：GitHub 仓库、HuggingFace 模型卡、ModelScope、Roboflow、媒体与社区文档），汇总如下：

## 视觉理解与视觉专项组件核实报告（DESIGN-LAB 适配评估）

| 组件 | 开发者 | 许可证 | 能力 | 维护状态 | 适配判断 | 许可证风险 |
|---|---|---|---|---|---|---|
| **CLIP** | OpenAI（[openai/CLIP](https://github.com/openai/
- [66] 不要只登记，能并入的就并入进来
- [67] 上传
- [68] 全面推进任务
- [69] <goal_round>
Objective: "全面推进后续任务：C1 Design IR 契约、C2 生产校验契约增强、C3 经验语料库契约、D1 Design Action Language、D2 质量分层管道定义，以及 A/B 组可自动化准备（Jury 评分工作包、来源补全辅助清单）。每项 fail-closed 验证 + 独立提交 + 全链保持 27/27。"
Round: 1/40

Continue working toward the objective in this same session. Treat the current workspace, tool results, and durable session state as authoritative; inspect them instead of assuming earlier narration is
- [70] <goal_complete>
Objective: "全面推进后续任务：C1 Design IR 契约、C2 生产校验契约增强、C3 经验语料库契约、D1 Design Action Language、D2 质量分层管道定义，以及 A/B 组可自动化准备（Jury 评分工作包、来源补全辅助清单）。每项 fail-closed 验证 + 独立提交 + 全链保持 27/27。"
The goal is marked complete and this autonomous run is ending. Write the closing message to the user now: state the outcome, summarize what was done and how it was verified, and point to the concrete results (f
- [71] 需要人工干什么？
- [72] 完整路径给我
- [73] 看不懂啊
- [74] 视频不行，是纯测试视频
- [75] 你现在能直接操控PS和OPEN DESIGN吗？
- [76] PS报错 APP.QUIT不是函数 直线10
- [77] Open Design  安装了啊
- [78] background job pwsh-32 (pwsh: & 'C:/Program Files/Adobe/Adobe Photoshop 2023/Photoshop.exe' -r 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/ps-smoke/smoke.jsx' 2>&1 | Select-Object -First 3; 'EXIT=' + $LASTEXITCODE; Start-Sleep -Seconds 3; Get-ChildItem 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/ps-smoke' | Select-Object Name, Length, LastWriteTime) finished [status: completed, exit code
- [79] 整理未完成的任务，还有WORKLAB推送到本项目的更新规划
- [80] 真实作品先不管，继续推进任务
- [81] 总结摘要，交接，归档，上传，双端一致
- [82] 执行所有未完成的开源项目吸收，不要只登记和放到历史记录里，吸收所有完成分析适合本项目的，全部沉淀到本项目里
- [83] 详细搜索怎么管理和操作设计类的软件（尽可能所有化，全面化，深度化）的开源项目
- [84] Background subagent 3fa1b0ab-d6b5-4960-86e3-10f6443549da reported:已用 web_search 完成 DESIGN-LAB 设计资产/设计系统管理开源工具全面调研，输出为 7 类 markdown 表格（DAM / 设计 token / DS 管理与文档 / 品牌资产库 / 字体 / 配色 / 版本管理），每项含①仓库与开发者②许可证③能力④维护状态⑤适配判断（可吸收源码/做 adapter/仅参考）。

关键结论：
- 吸收源码：Style Dictionary（Apache-2.0，token 流水线）、primer/prism（配色算法）、culori/chroma.js（色彩库）。
- 做 adapter：DTCG JSON 格式（对齐 Tokens Studio 生态）、Storybook。
- 仅参考：Resour
- [85] Background subagent 618d8b1c-b86b-4ad6-9d67-563333ef4b2b reported:## 操作设计软件开源库/脚本生态调研完成（web_search 逐项核实）

完整报告已落盘：**research/design-software-oss-ecosystem.md**（含来源链接）。

### 总表

| 项目 | 开发者 | 许可证 | 操作能力 | 维护 | 适配判断 |
|---|---|---|---|---|---|
| uxp-toolkit | bubblydoo | MIT | 构建 Photoshop UXP 插件的 TS/JS 工具集（UI/PS API 封装/打包） | 维护中 | 仅参考（Adobe 私有平台，无法 vendored；至多做 adapter 生成/驱动插件） |
| ExtendScript（Adob
- [86] Background subagent 3fa1b0ab-d6b5-4960-86e3-10f6443549da finished and will do no further work unless you send it more.Its closing message:调研已完成并上报。完整结果（7 类工具、30+ 条目、全部经真实检索、未核实字段已标注）见上方 markdown 表格。要点回顾：

- **可吸收源码**：Style Dictionary（token 流水线，Apache-2.0）、primer/prism（配色算法）、culori/chroma.js（色彩引擎）
- **做 adapter**：DTCG JSON 格式（对齐 Tokens Studio）、Storybook
- **仅参考**：ResourceSpace / Razuna（停更）/ Piwigo、
- [87] Background subagent 618d8b1c-b86b-4ad6-9d67-563333ef4b2b finished and will do no further work unless you send it more.Its closing message:调研完成。基于 **29 次真实 web_search**（仓库页、LICENSE 文件、发布记录、relicense 公告逐一核实），完整报告已写入 `research/design-software-oss-ecosystem.md`。核心交付如下：

## 总表（项目 | 开发者 | 许可证 | 操作能力 | 维护 | 适配判断）

| 项目 | 开发者 | 许可证 | 操作能力 | 维护 | 适配判断 |
|---|---|---|---|---|---|
| uxp-toolkit | bubblydoo |
- [88] Background subagent e2606ffe-2484-41b5-a47f-829b41abafbe finished and will do no further work unless you send it more.Its closing message:**调研完成。** 已把结论写入今日日志与项目笔记。以下为完整交付。

---

## 调研方法与边界

- 全部经 `web_search` 真实检索核实仓库存在性、发布版本、维护动态；许可证以项目官方信息 + 行业常识交叉确认。
- 本次搜索后端主要返回 URL 清单（摘要字段多为空），故 **①仓库/开发者、④维护状态（版本号/发布日期）为搜索直接证实**；**②许可证文本未能逐字读取的，以项目官方声明为准**，少数不确定项已标注。
- DESIGN-LAB 背景（据工作区扫描）：AI 设计指挥中心式管线——任务
- [89] 所有未完成的任务全部执行（所有任务），全量推进，直到闭环
- [90] background job pwsh-14 (pwsh: & 'C:/Program Files/Adobe/Adobe Photoshop 2023/Photoshop.exe' -r 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/ps-real/g1-hero.jsx' 2>&1 | Select-Object -First 3; 'EXIT=' + $LASTEXITCODE) finished [status: completed, exit code: 0]. Read its output with job_output.
- [91] background job pwsh-16 (pwsh: & 'C:/Program Files/Adobe/Adobe Photoshop 2023/Photoshop.exe' -r 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/ps-real/g1-final.jsx' 2>&1 | Select-Object -First 3; 'EXIT=' + $LASTEXITCODE) finished [status: completed, exit code: 0]. Read its output with job_output.
- [92] background job pwsh-15 (pwsh: & 'C:/Program Files/Adobe/Adobe Photoshop 2023/Photoshop.exe' -r 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/ps-real/g1-simple.jsx' 2>&1 | Select-Object -First 3; 'EXIT=' + $LASTEXITCODE) finished [status: completed, exit code: 0]. Read its output with job_output.
- [93] background job pwsh-17 (pwsh: & 'C:/Program Files/Adobe/Adobe Photoshop 2023/Photoshop.exe' -r 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/ps-real/g1-no-target.jsx' 2>&1 | Select-Object -First 3; 'EXIT=' + $LASTEXITCODE) finished [status: completed, exit code: 0]. Read its output with job_output.
- [94] 清理废弃文件和冗余文件，总结 摘要 交接 上传 双端（本地和云端仓库）一致
- [95] 有WORK-LAB项目推过来的文档，看下
- [96] 全部执行，全部完成
- [97] 人工延后，执行完所有其他任务
- [98] 执行完所有未完成任务
(不含知识迁移，OS为完善，等我明确指令，先归档到本项目里)
- [99] 重点完成对设计软件的操控
- [100] background job pwsh-19 (pwsh: & 'C:/Program Files/Adobe/Adobe Photoshop 2023/Photoshop.exe' -r 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/ps-debug/smoke2.jsx' 2>&1 | Select-Object -First 2; 'EXIT=' + $LASTEXITCODE; Start-Sleep -Seconds 5; Get-ChildItem 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/ps-debug' -Filter '*.psd' | Select-Object Name, Length) finished [status: completed, exit co
- [101] background job pwsh-20 (pwsh: Get-Process -Name Photoshop -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; & 'C:/Program Files/Adobe/Adobe Photoshop 2023/Photoshop.exe' -r 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/ps-debug/smoke3.jsx' 2>&1 | Select-Object -First 2; 'EXIT=' + $LASTEXITCODE) finished [status: completed, exit code: 0]. Read its output with job
- [102] background job pwsh-22 (pwsh: Get-Process -Name Photoshop -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; & 'C:/Program Files/Adobe/Adobe Photoshop 2023/Photoshop.exe' -r 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/ps-debug/smoke3d.jsx' 2>&1 | Select-Object -First 2; 'EXIT=' + $LASTEXITCODE) finished [status: completed, exit code: 0]. Read its output with jo
- [103] background job pwsh-25 (pwsh: & 'C:/Program Files/Adobe/Adobe Photoshop 2023/Photoshop.exe' -r 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/ps-debug/g1-stable.jsx' 2>&1 | Select-Object -First 2; 'EXIT=' + $LASTEXITCODE) finished [status: completed, exit code: 0]. Read its output with job_output.
- [104] background job pwsh-26 (pwsh: & 'C:/Program Files/Adobe/Adobe Photoshop 2023/Photoshop.exe' -r 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/ps-debug/g1-final2.jsx' 2>&1 | Select-Object -First 2; 'EXIT=' + $LASTEXITCODE) finished [status: completed, exit code: 0]. Read its output with job_output.
- [105] background job pwsh-28 (pwsh: '--- 彻底清理 PS 全部进程 ---'; Get-Process | Where-Object { $_.Name -match 'Photoshop|Adobe' } | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 3; '残留: ' + (Get-Process | Where-Object { $_.Name -match 'Photoshop' } | Measure-Object).Count; '--- 冷启动 G1-final2 ---'; & 'C:/Program Files/Adobe/Adobe Photoshop 2023/Photoshop.exe' -r 'D:/All projects/DESIG
- [106] background job pwsh-29 (pwsh: Get-Process -Name Photoshop -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 3; '--- 原 smoke2.jsx 重跑 ---'; & 'C:/Program Files/Adobe/Adobe Photoshop 2023/Photoshop.exe' -r 'D:/All projects/DESIGN-LAB/.hermes/task-runtime/ps-debug/smoke2.jsx' 2>&1 | Select-Object -First 2; 'EXIT=' + $LASTEXITCODE) finished [status:
- [107] 找项目，找同行，找同类，找同源，找开源，增强项目，尤其是增强操作能力
- [108] Background subagent bdb993e4-da5a-4d8b-baef-b474a3c66e2e reported:DESIGN-LAB 同源/同名/相近项目调研完成（本地文件 + GitHub API/HTTP 双重核实，无臆造）。

## ① OPEN-DESIGN-Assistance（本项目迁移源/前身）历史与迁移链
- 身份链：WORK-LAB(20-design/open-design/ 目录) → OPEN-DESIGN-Assistance 身份（曾用名 Open Design Assistance / opendesign-assistance / Design Intelligence Layer / Design Intelligence Capability Kit，均已退出活动命名）→ DESIGN-LAB
- 迁移：2026-08-07 任务 W
- [109] Background subagent bdb993e4-da5a-4d8b-baef-b474a3c66e2e finished and will do no further work unless you send it more.Its closing message:# DESIGN-LAB 同源/同名/相近项目调研报告

**方法**：本地文件核实（README、迁移文档、history 归档、SBOM、QUARANTINE_REGISTRY）+ web_search 定位候选 + GitHub API / HTTP 双重验证（仓库存在性、star、license、归档状态）。全部真实核实，无臆造。

---

## ① OPEN-DESIGN-Assistance：历史与迁移链（本地证据）

**身份链**：`WORK-LAB`（`20-design/open-design/`
- [110] Background subagent d60508d5-7e15-4d0e-8b14-bac1e2421bc8 reported:# AI 设计类同行调研报告（2024–2026）—— 对标 DESIGN-LAB

**方法说明**：真实 web_search（4 轮共 38 个查询，来源链接见各条目）；并用 pwsh 直接抓取 GitHub raw LICENSE 文件实测确认 5 个开源仓库许可证（screenshot-to-code=MIT、OpenUI=Apache-2.0、v0.diy 两仓库=MIT、tldraw make-real-starter=AGPL-3.0）。无法核实处明确标注 [未核实]，未臆造。

## 一、商业产品 / 平台（AI 设计生成、design intelligence）

| 项目 | 公司 | 许可证 | 核心能力 | 差异化 / 借鉴 | 增强
- [111] Background subagent d60508d5-7e15-4d0e-8b14-bac1e2421bc8 finished and will do no further work unless you send it more.Its closing message:调研已完成并交付。以下是核心结论摘要：

## 调研方法
- 真实 web_search 4 轮共 38 个查询，覆盖用户指定的全部 14 个商业产品 + 开源 agentic design 项目
- 用 pwsh 直接抓取 GitHub raw LICENSE 文件**实测核实**了 5 个仓库许可证，非猜测
- 无法核实处均标注 `[未核实]`，未臆造

## 关键发现

**商业产品（16 项核实）**：v0/Vercel（闭源商业，shadcn/ui MIT）、Galileo AI（商业，产设计稿最接近本项目形
- [112] Background subagent 8ee9d2bc-8f4d-4fe9-8586-2a578d56078c reported:# 增强设计软件操作能力的开源项目调研（6 大类，web_search + GitHub/npm/PyPI API 双重核实）

## ① Photoshop / Illustrator 自动化开源
| 项目 | 仓库 | 许可证 | 能力 | 维护状态 | 对本项目价值 |
|---|---|---|---|---|---|
| psd-tools (Python) | psd-tools/psd-tools | MIT | 读取/渲染 PSD/PSB：图层、蒙版、混合模式、文本、智能对象；导出 PNG/JPEG/PSD→CSS 样式 | 活跃：1,443★，最后推送 2026-08-17，PyPI v1.18.0 | 吸收：Python 侧 PSD 解析/
- [113] Background subagent 8ee9d2bc-8f4d-4fe9-8586-2a578d56078c finished and will do no further work unless you send it more.Its closing message:调研完成。方法：`web_search` 真实检索 + GitHub API（星标/许可证/最后推送/是否归档）+ npm/PyPI registry（最新版本/发布时间）双重核实，限流处明确标注未核实。**已把结论记入今日日志**（`DESIGN-LAB/2026-08-19.md`）。

# 增强设计软件操作能力的开源项目调研（6 大类）

## ① Photoshop / Illustrator 自动化开源

| 项目 | 仓库 | 许可证 | 能力 | 维护状态 | 对本项目价值 |
|---|---|---|
- [114] 接入
- [115] PS和ILLUSTRATOR的所有功能是不是都能用了
- [116] 网上没有吗？
- [117] 可以纳入网上经过验证的方案到项目里啊，可以留存归档，不就不用你做了吗
- [118] 扩大范围找项目里所有对应的设计软件的自动化脚本转化纳入进来
- [119] Background subagent 04149d33-5525-49e1-affd-8e09b66355a2 reported:四类开源设计软件自动化脚本核实完成(2026-08-19, GitHub API + npm registry + HTTP HEAD 实测, 非臆造)。关键事实:
- Blender: njanakiev/blender-scripting 821★ MIT(2021停更,教程配套可下载); Tlousky/blender_scripts 162★ 无license(2025活跃); amb/blender-scripts 45★ 无license(2023停更); BlenderKit/headless-blender-container 16★ 无license(2026活跃,无头容器批渲染); Vittorio-Caggiano/blender-cli
- [120] Background subagent 04149d33-5525-49e1-affd-8e09b66355a2 finished and will do no further work unless you send it more.Its closing message:**已更新今日日志**（四类脚本仓库核实结论已记入 2026-08-19 日志）。

# 开源设计软件已验证自动化脚本（2026-08-19 实测核实）

核实方式：GitHub API（星数/许可证/最后推送/归档状态）+ npm registry + HTTP 状态码检查，均为真实数据。所有仓库 URL 可直接点击。

## ① Blender Python 脚本集合（bpy 批处理：建模/渲染/导出）

| 仓库 | 许可证 | 星数·维护 | 脚本功能 | 能否转化纳入 |
|---|---|---|---|-
- [121] Background subagent e1792d7c-e4d5-422f-a697-a2c43eff8d53 reported:四类生成与自动化工具脚本调研完成（真实 web_search + GitHub API/jsDelivr/raw 实测，星标/许可证为 2026-08-19 实测值，未验证项已标注）：
①ComfyUI workflow 模板：Comfy-Org/workflow_templates(MIT,818★,官方,templates/ 数百 JSON+预览,单文件 raw 直链可下载)；comfyui-wiki/ComfyUI-Wiki-Workflows(19★,⚠️无 LICENSE 需确认授权,example_workflows/ JSON+JPG)；mcphub-com/awesome-comfyui-templates(150 文件实为 JSON 合集,⚠
- [122] Background subagent e1792d7c-e4d5-422f-a697-a2c43eff8d53 finished and will do no further work unless you send it more.Its closing message:调研已完成并交付（正文上方为完整 markdown 表格），结果已上报父代理并写入今日日志。

**收尾摘要：**
- ✅ 四类主题全部真实搜索 + 实测核实（GitHub API 许可证/星标、jsDelivr 目录树、raw 文件探测、svgo README 原文），**无臆造项**——两个 404 仓库（gunthercox/ffmpeg-batch、resvg/resvg 旧路径）已排除，resvg 确认迁移至 linebender 组织（Apache-2.0）。
- ✅ 每类给出可直接下载的脚本/workfl
- [123] Background subagent afd2e93d-92f4-41a4-8e61-0dd4edc40d24 finished and will do no further work unless you send it more.Its closing message:调研完成，报告已发送给父 agent。以下是完整结果摘要：

# Adobe 系 + 矢量软件已验证自动化脚本库/集合调研结果

**方法**：web_search 定位候选 → GitHub REST API 实测 stars/license/pushed_at/archived → raw.githubusercontent.com 核实 LICENSE 文件与 README。全部数据为实测值。

## ① Photoshop ExtendScript/JSX 脚本集合

| 仓库 | 许可证 | 脚本功能 | 维
- [124] Background subagent afd2e93d-92f4-41a4-8e61-0dd4edc40d24 reported:# Adobe 系 + 矢量软件已验证自动化脚本库/集合调研结果（真实搜索 + GitHub API + raw 文件核实，2026-08-19）

调研方法：web_search 定位候选 → GitHub REST API 核实 stars/license/pushed_at/archived → raw.githubusercontent.com 读取 LICENSE 文件与 README 核实功能与授权声明。所有 star 数、许可证、最后推送时间均为 API 实测值，非臆造。

## ① Photoshop ExtendScript/JSX 脚本集合

| 仓库 | 许可证 | 脚本功能 | 维护 | 转化建议 |
|---|---|---|---|
- [125] 总结摘要交接文档，上传，双端一致
- [126] 对了本项目要接入eagle 去官网查下
- [127] "D:\Program Files\Eagle\Eagle.exe"  你是检测不到吗？这个不就是吗
- [128] 上传，本地云端仓库一致

**我执行的工具:** run_code, todo_write, write, read

**我的结论:** 

---

## 三、记忆
### 2026-08-18.md

- 23:47 web_search 调研开源设计软件与设计自动化管线(4 大类约 25 项): Penpot/Inkscape/GIMP/Krita/Pencil2D/Synfig/Gravit, Chromatic/Style Dictionary/W3C DTCG/Tokens Studio, veraPDF/Ghostscript/导出管线, BackstopJS/Lost Pixel/Argos/pixelmatch/Playwright 等; 输出仓库/许可证/能力/维护状态/对 DESIGN-LAB 适配判断(吸收/adapter/仅参考) markdown 表格。

---

### 2026-08-19.md

- 00:28 web_search+GitHub API 调研 DESIGN-LAB 同源/同名/相近项目：①前身 OPEN-DESIGN-Assistance 迁移链核实（WORK-LAB 20-design/open-design → migration/work-lab-design-extraction-20260807 分支(2026-08-07, 493文件manifest) → DTALEX66/DESIGN-LAB；opendesign-assistance/ 427文件 git mv→design-lab/；旧名301重定向至 DESIGN-LAB；ODA4 报告归档 reports/history/）；②同名搜索：hdl-eda/digital-ic-design-lab(9★教学)、xupsh/Digital-Design-Lab(233★)、google-labs-code/design.md(27.4k★ Apache-2.0 DESIGN.md格式规范，本地已vendored进SBOM)、0xdesign/design-plugin(747★ design-lab skill)、designlab.com教育；③相近定位：nexu-io/open-design(89.3k★ Apache-2.0 Claude Design开源替代，本项目reference host！本地OPEN_DESIGN_ENHANCEMENT_RESEARCH.md记录)、superdesigndev/superdesign(6.9k★ TypeScript)、Nutlope/hallmark(25.8k★ MIT 本地P0吸收)、JimLiu/baoyu-design(3.5k★ MIT P1)、VoltAgent/awesome-design-md(109k★ MIT P0)、ZeroZ-lab/cc-design(825★)、W3C DTCG/pixelmatch 已vendored
- 00:29 web_search+GitHub/npm/PyPI API 调研【增强设计软件操作能力的开源项目】6 大类约 30 项：①PS/AI 自动化(psd-tools MIT 1.44k★活跃、ag-psd 701★活跃、psd.js 2.8k★维护放缓、AdobeDocs/uxp、ie3jp/illustrator-mcp-server 81★) ②Figma(figma-js 上游404仅归档fork勿用、@figma/rest-api-spec 官方活跃215★、Tokens Studio+token-transformer、figma-developer-mcp v0.13.2) ③Inkscape GPL-2.0 CLI批量导出/Blender bpy无头/GIMP批处理+HKUDS/CLI-Anything 47.8k★ agent-harness封装模式 ④解析库(sharp Apache-2.0 32.6k★、resvg Apache-2.0 4k★、pdf-lib MIT 8.6k★维护放缓、satori MPL-2.0) ⑤MCP(photoshop-mcp 322★ MIT 102工具 Windows-first变体、figma官方guide 1.9k★、inkscape-mcps 54★、Adobe官方generator-app-remote-mcp Apache-2.0；PyPI adobe-mcp是第三方VoidChecksum非官方) ⑥框架(style-dictionary Apache-2.0 4.8k★活跃、pixelmatch ISC、BackstopJS 7.2k★维护放缓、lost-pixel)。结论:吸收 ag-psd/pixelmatch/style-dictionary/sharp/resvg; adapter Inkscape CLI/Figma REST+MCP/Photoshop MCP/CLI-Anything harness模式; 参考 psd.js/figma-js/BackstopJS/Theo/GIMP批处理。
- 00:51 web_search 核实四类开源设计软件自动化脚本仓库(GitHub API+npm 实测): Blender→njanakiev/blender-scripting(MIT 821★ 停更)/Tlousky 162★ 无license/BlenderKit headless容器活跃; GIMP→kritiksoman/GIMP-ML(MIT 1558★)/gummyCowboy GPL-3.0/vm-felipe gimp3 MIT, registry.gimp.org_static 已404下线; Figma→figma/plugin-samples(MIT 1842★ 官方)/yuanqing create-figma-plugin(MIT 1115★)/figma-plugin-ds(MIT 756★); Penpot→penpot-plugins 已归档MPL-2.0, samples MIT 22★ 替代, starter-template MIT 41★, @penpot/mcp v2.15.4 官方MCP。
- 00:52 核实 Adobe 系+矢量软件自动化脚本库清单(GitHub API+raw 实测): PS→creold/photoshop-scripts(MIT 139★ 2025-05)/ES-Collection 103★无LICENSE/kynd 63★无LICENSE/GPL-3.0 Batch-Export-Artboard-To-JPG; AI→creold/illustrator-scripts(MIT 1091★ 2026-07 活跃 100+脚本 Downloads 212k)/sky-chaser-high(MIT 200★ 2026-03)/joshbduncan(MIT 45★ 2026-04); Inkscape→SimpInkScr(GPL-3.0 436★ 2026-07 活跃 Python脚本驱动)/berteh/svg-objects-export(116★ 无LICENSE 单文件py)/StefanTraistaru/batch-export(MIT 71★ 扩展 按图层导出)/leifgehrmann/svg-stroke-to-path(MIT 36★ 已archived)。无LICENSE仓库默认保留权利不可直接纳入;MIT首选直接下载+SPDX头+归档
- 00:52 web_search+GitHub API/jsDelivr/raw 核实四类生成与自动化脚本仓库: ①ComfyUI workflow模板 Comfy-Org/workflow_templates(MIT 818★ 官方 templates/数百JSON+预览, raw直链可下载)/comfyui-wiki(MIT无LICENSE 19★ 需确认授权)/mcphub-awesome-comfyui-templates(150文件实为JSON合集, 许可证未核实) ②ffmpeg批处理 Thqrn/ffmpeg-scripts(GPL-3.0 20★ .bat拖放抽帧转码)/Munna-Soft/FFmpeg-Batch-Tools-Collection(MIT 7★ 25个.bat)/PhotonFrame-VideoKit(MIT 4★ Python模块化CLI+AI放大) ③SVG svgo(MIT 22.6k★ README原文确认 svgo -rf 目录批量)/linebender/resvg(Apache-2.0 4k★ resvg-py MIT 8★)/rsvg-convert(LGPL librsvg, MSYS2安装) ④Style Dictionary style-dictionary(Apache-2.0 4.8k★ examples/basic+advanced/s3 完整build.js模板可直接复制)/awesome-design-tokens(Apache-2.0 10★ 多品牌token+SD输出模板)/tokens-studio/plugin-example-multi(MIT 36★)。结论: 除comfyui-wiki与mcphub许可证未落实外均宽松许可可纳入DESIGN-LAB管线

---

### MEMORY.md


## 2026-08-18
## 2026-08-18 开源设计软件与设计自动化管线调研结论(web_search 核实)
- 直接适配(DESIGN-LAB): Penpot(adapter, 07 备份规则已有基础, REST 导出 SVG/PDF)、Inkscape CLI(批量 SVG→PDF/PNG)、Style Dictionary(token JSON→CSS/Android 资源, 与 10_DESIGN_TOKEN_SYSTEM 对接)、Playwright toHaveScreenshot(v5-runtime 多尺寸截图对比)、pixelmatch(轻量 diff 引擎, 可吸收)、rsvg-convert/cairosvg/ImageMagick/sharp(批量导出)。
- 可选 adapter: veraPDF(PDF/X-1a/3、PDF/A 校验门禁, v1.26+)、Ghostscript(PDF 渲染/压缩)。
- 仅参考: GIMP/Krita/Pencil2D/Synfig(非管线核心)、Gravit(已停服)、Chromatic(商业 SaaS, CLI MIT)、Tokens Studio(无开源许可, 借鉴 Git 同步工作流)、W3C DTCG(token 格式对齐)、BackstopJS/Lost Pixel/Argos/reg-suit/resemble.js(视觉回归 CI 思路)。
- 关键事实: Penpot 2.4.0(2024-12)、GIMP 3.0(2025-03)、Inkscape 1.4(2024-10)、veraPDF v1.30.2(2026-06)、Style Dictionary v4 社区治理、chromatic-cli v17。

## 2026-08-19
## 2026-08-19 Adobe系+矢量软件脚本库调研补充(web_search+GitHub API 实测)
- 首选直接纳入(MIT, 可直接下载脚本本体+SPDX头+归档): creold/illustrator-scripts(1091★, 100+ jsx, 画板/导出/路径/文字/颜色, 2026-07 活跃, 212k下载), creold/photoshop-scripts(139★, 11个jsx: ArtboardsFromCSV/ExportPathsToAi/GeneratePreview/SaveAll/SelectShapesByColor/TIFF2Print), sky-chaser-high/adobe-illustrator-scripts(200★, 分类齐全含Artboard/Color, 有Release zip), joshbduncan/illustrator-scripts(45★, Alignment/Artboard/Color/Layer/Path/Production/Selection), StefanTraistaru/batch-export(71★, Inkscape扩展按图层导出SVG/PNG/PDF/EPS等), leifgehrmann/svg-stroke-to-path(MIT 36★ 但已archived 2026)
- 无LICENSE默认保留权利不可直接纳入(仅参考): ES-Collection/Photoshop-Scripts 103★, kynd/photoshopScripts 63★ 2013停滞, berteh/svg-objects-export 116★(单文件py 按ID/regex/XPath导出元素)
- GPL-3.0 注意传染性: spakin/SimpInkScr(436★ 活跃, Python脚本驱动Inkscape画布), abdul-karim-mia/Batch-Export-Artboard-To-JPG(6★ PSD画板批量JPG)
- Inkscape 官方 gallery 另有 'Inkscape batch convert' 扩展(inkscape.org 页面)
- 转化流程: 下载脚本本体→加SPDX许可证头(记录来源URL+commit)→归档, MIT 类可直接做

---

## 四、历史文档/蓝图/冻结线（归档）
### DESIGN-LAB-TOTAL-SUMMARY.md

# DESIGN-LAB 项目总文档（所有软件会话 + 历史汇总）

> 生成：2026-08-24 | 数据源：HERMES/CODEX/DSH 会话 + 90-archive 归档 + 项目文档

## 1. 项目定位
- 三项目分层 v5 的【设计能力所有者】
- 设计能力（models/tools/generation params/assets/specs/quality gates）归 DESIGN-LAB，WORK-LAB 保持 IGNORE
- 648 个设计专家技能库（b2b-backoffice/brand-identity/ecommerce-pdp 等）

## 2. 会话历史（各软件）

### DSH 会话（dsh-home/sessions/DESIGN-LAB）：13 文件
### Codex 会话（session_index.jsonl）：涉及像素级复刻/设计相关
### Open Design：外部设计客户端（nexu-io/open-design），不代表 DESIGN-LAB 本体

## 3. 归档文档索引（90-archive/session-history/DESIGN-LAB，9 docs）
- timeline.md（时间线）
- ABSORPTION_PLAN.md（吸收计划）
- BOUNDARY_CONTRACT.md + BOUNDARY_CONTRACT_V42.md（边界契约 v4.2）
- MIGRATION_STATUS.md（迁移状态）
- MINIGAME_RUNTIME_CLEANUP.md（小游戏运行时清理）
- OPEN_DESIGN_V3_PHASE2_HANDOFF.md（Open Design V3 Phase2 交接）
- TP-20260819-TASKPACK-DESIGNLAB.md（联邦任务包）
- V4_MIGRATION_FINAL_STATE.md（V4 迁移最终状态）

## 4. 关键状态（2026-08-24）
- AGENTS.md 已补（含全局标准 + LESSONS_LEARNED 引用）
- 当前分支 codex/pixel-perfect-vector-reconstruction（ahead 29/behind 1，DIVERGED）
- 未跟踪交接：PIXEL_PERFECT_VECTOR_RECONSTRUCTION_HANDOFF（保留）
- 漂移基线 BLOCKED（治理文件不干净）
- WL-DLC 任务包反馈：治理代码落地但运行态收尾项明确

## 5. 冻结线路/契约
- 边界契约 v4.2（BOUNDARY_CONTRACT_V42）
- V4 迁移最终状态
- 全局边界（E盘禁访/数据边界/官方优先）
- 设计能力 IGNORE（WORK-LAB 不采集不管理）

---
