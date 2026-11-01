# ComfyUI 适配器 — 权利与 Provider 策略

- **任务**：DL-CFY-001（ComfyUI 适配器）/ DL-CFY-002（ComfyUI 取证）
- **状态**：历史声明保留；当前资格按 R3-16 账本与本轮实际工作流证据判定，不从旧 E3 推导当前可用
- **运行时**：本机已有 ComfyUI portable，定位见根 `docs/LOCAL_ENVIRONMENT.md` 与 `.project/paths.json`；文件存在不替代服务/节点/推理验证

## 权利

- ComfyUI 本体：GPL-3.0（开源）；自定义节点许可各异（使用前逐节点核验）
- 生成资产：用户拥有（本工具不主张权利），但**商用/分发权利受模型许可与 Provider 条款约束**
- 模型权重：按各自固定 revision 的许可及用途/地区条件审查；历史 H3 sidecar 的 redistributable=false / commercialUse=false 作为既有产物限制保留，不代替当前模型资格或新的权利批准
- H3 产物权利：见 minimax-h3 evidence sidecar（内部验证用，未验证分发/商用）

## Provider 策略

- **模型路由**：ComfyUI 本地推理（loopback-only，绑定 127.0.0.1），不走远程 provider
- **启动**：手动启动（manual launch）——用户自行启动 ComfyUI 后适配器才可连接
- **无 rate limit / 无 cost cap**：本地 GPU 推理，不设人为限制
- **reasoning 降级**：不适用（推理在模型自身，不干预）
- **凭证**：不读取、不存储任何 API key（本地节点除外，用户自管）

## 边界

- 运行/缓存/临时文件写本项目 `.project-local/task-runtime/`，证据写 `.project-local/task-artifacts/`，持久作品走资产服务；实际路径由根 `.project/paths.json` / `PROJECT_LOCAL_ROOT` 解析
- `80-evidence/`、`.hermes/` 仅保留历史定位，不新写，也不据此迁移或删除旧内容
- 不访问 `E:\`；不触碰共享运行时状态
- 进程隔离：ComfyUI 以独立进程运行，不修改宿主配置

## 取证（E3 恢复条件）

1. 绑定代码/适配器/宿主与节点版本、模型 revision/hash、完整工作流指纹、OS、输入与产物 hash、授权
2. 真实 loopback workflow 完成并按任务身份读回历史及产物；缓存复用不冒充新推理
3. 验证取消对账、断线恢复、失败和回滚；固定合成样例最多证明对应受控运行，不以一次 txt2img 或退出码宣称 E3
4. 按根 AGENTS 的真实工作流要求及 Human Gate 独立验收
