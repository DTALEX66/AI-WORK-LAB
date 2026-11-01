# MiniMax H3 适配器 — 权利与 Provider 策略

- **任务**：DL-H3-001（H3 适配器）/ DL-H3-002（H3 取证）/ DL-H3-003（H3-Comfy 桥接）
- **状态**：历史声明保留；当前本地推理资格按 R3-19 及对应新鲜证据判定
- **运行时**：用户已提供本机 H3 模型；位置见根 `docs/LOCAL_ENVIRONMENT.md` 与 `.project/paths.json`，完整权重、实际加载/推理须分别校验

## 权利

- H3 模型：按固定上游 revision 的实际 LICENSE、用途/地区条件与权重来源审查，不从安装、订阅或时区推定授权；不 vendoring 权重
- 生成视频：本工具不主张权利；输入素材和模型/生成内容的适用限制须独立审查
- 桥接：`h3-comfy-bridge-feasibility.md` 为可行性分析（不含受版权保护的实现）

## Provider 策略

- **模型路由**：本专项验证 H3 本地推理，不用官方云端、其他模型或缓存替代本地成功；任何新增远端调用须另有授权
- **无 rate limit / 无 cost cap**：不设人为限制（遵循官方服务条款）
- **reasoning 降级**：不适用（视频生成模型）
- **凭证**：不读取 API key（用户自管官方凭据）

## 边界

- 运行/缓存/临时文件写本项目 `.project-local/task-runtime/`，证据写 `.project-local/task-artifacts/`，持久作品走资产服务；实际路径由根 `.project/paths.json` / `PROJECT_LOCAL_ROOT` 解析
- `80-evidence/`、`.hermes/` 仅保留历史定位，不新写，也不据此迁移或删除旧内容
- 不访问 `E:\`；不触碰共享运行时状态
- 进程隔离：H3 以独立进程运行，不修改宿主配置

## 取证（E3 恢复条件）

1. 固定模型/推理代码 revision、完整权重 hash、许可适用条件；独立核实 RAM/VRAM 与算子兼容
2. 实际本地最小生成任务，记录加载/推理、峰值资源、输入/产物 hash、时间与媒体读回
3. 绑定当前代码/适配器/宿主版本、OS、任务授权、失败恢复与回滚；短样例不直接等于完整 E3 工作流
4. 只在实际推理与输出校验通过后标 LOCAL_INFERENCE_VERIFIED；H3 的具体阻塞不扩散为全项目阻塞，Human Gate 不代签
