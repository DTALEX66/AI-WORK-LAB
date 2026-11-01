# DESIGN-LAB Deep Research — Child E：MiniMax 官方 + ComfyUI 官方 API 核实（纯 Web 研究）

你是集成研究工程师。目标：用官方事实判定 (1) MiniMax Design 是否提供稳定的公开接口可被 DESIGN-LAB 调用（尤其能否配置 arbitrary ComfyUI base URL 如 http://127.0.0.1:8188）；(2) ComfyUI 核心 server API 官方契约全集；(3) H3 模型是否有官方 ComfyUI 路径。

## 硬性规则
- 只用 web_search / web_extract。Primary sources：MiniMax 官网/官方 docs/官方 GitHub（MiniMax-AI）；ComfyUI 官方 GitHub（comfyanonymous/ComfyUI）源码与 docs。
- 每个结论标等级：CONFIRMED_OFFICIAL / CONFIRMED_CODE（官方仓库源码）/ INFERRED / UNCONFIRMED（官方未披露 → 写「机制未公开」，禁止从 UI 演示推断 API 存在）。
- **不因 "MiniMax Design 能操作 Photoshop" 就推断暴露稳定 Photoshop API**，也不推断其能控制 Illustrator/Premiere/AE/InDesign/Bridge/Acrobat —— 逐 host 单独判断（若官方披露了范围）。
- 中文输出。

## 研究任务
1. **MiniMax Design 产品形态**：官方定位（创意 Agent？桌面 App？Web？）、官方 docs 公布的接口（开放 API？插件协议？），是否能作为「稳定公开协议」被外部 Control Plane 调用。
2. **MiniMax + ComfyUI 集成**：是否存在官方 ComfyUI 节点/插件？是官方 plugin integration 还是通用 endpoint？是否支持用户自定义 base URL（127.0.0.1:8188 任意 ComfyUI 实例）？官方文档原文引用。
3. **H3（MiniMax 模型）**：H3 在 ComfyUI 中的官方路径（官方 node 包？第三方 node 包？）；第三方 node 包 → 供应链风险注记。
4. **ComfyUI 官方 server API 全集核实**（对照 comfyanonymous/ComfyUI 源码 server.py / 官方 docs，逐端点给 file 证据）：
   POST /prompt、GET /history、GET /history/{prompt_id}、GET /view、GET /system_stats、GET /object_info、POST /upload/image、/ws（websocket）、POST /interrupt、POST /queue、/sd_models 等 —— 哪些是官方源码确认、语义（同步/异步 prompt_id 模型）、版本稳定性承诺（是否保证 API 不破坏）。
5. **推荐架构判定**：DESIGN-LAB → ComfyUIAdapter → 本地 ComfyUI(:8188) → H3 这条链路中每一环的官方证据等级；MiniMax Design 在 DESIGN-LAB 中的合理定位（Creative Agent / Canvas / Human Interaction / Asset Bridge vs Control Plane）—— 只基于公开稳定接口判断，无稳定接口就判 ASSET_BRIDGE。
6. 安全：MiniMax license/公开契约、ComfyUI custom-node 供应链（第三方 node 执行权限）。

## 输出格式（最终答案必须是该 JSON）
{"summary": "<12行内中文结论：MiniMax 可否做控制层（一句话判定+理由）/ H3 官方 ComfyUI 路径有无 / ComfyUI API 官方确认清单 / 推荐架构>",
 "minimax_design": {"official_form":"...","public_protocol":"CONFIRMED/UNCONFIRMED + URL","arbitrary_comfyui_url":"CONFIRMED/UNCONFIRMED + 证据","ps_control_mechanism":"官方披露 or 机制未公开","official_evidence_urls":[...]},
 "h3_comfyui": {"official_path":"CONFIRMED/UNCONFIRMED","third_party_supply_chain_risk":"...","evidence":[...]},
 "comfyui_api": [
   {"endpoint":"POST /prompt","status":"CONFIRMED_CODE (server.py:...)","semantics":"..."}, ...],
 "recommended_architecture": {"control_plane":"DESIGN-LAB","minimax_role":"...","comfyui_adapter":"...","confidence":"...", "caveats":[...]},
 "defects_or_risks": ["..."],
 "evidence_refs": ["URL/仓库 file + 等级", ...],
 "blocked": ["未能确证项", ...]}
