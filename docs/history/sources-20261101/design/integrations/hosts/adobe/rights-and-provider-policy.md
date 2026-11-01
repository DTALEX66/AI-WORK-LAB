# Adobe Photoshop 适配器 — 权利与 Provider 策略

- **任务**：DL-ADB-PS-001（Photoshop 适配器 E3）
- **状态**：本页保留 DL-ADB-PS-001 历史声明；当前按 R3-12 账本与对应宿主证据判定，不因安装登记宣称产品桥可用
- **运行时**：Adobe Photoshop（用户侧安装，需订阅）

## 权利

- Photoshop 本体：proprietary（Adobe 订阅制）——仅作为运行时宿主，不 vendoring
- 脚本契约：通过官方脚本/UXP 接口调用（不逆向、不破解）
- 生成资产：本工具不主张权利；第三方图片、字体等仍需逐项记录来源、许可范围和必要批准，不能仅凭生成动作宣称权利已满足

## Provider 策略

- **模型路由**：本地 Photoshop 进程，不走远程 provider
- **无 rate limit / 无 cost cap**：本地执行，不设人为限制
- **reasoning 降级**：不适用（Photoshop 非模型推理）
- **凭证**：不读取 Adobe 账号凭据；订阅状态用户自管

## 边界

- 项目运行、缓存和临时文件写入 `.project-local/task-runtime/`；审计证据写入 `.project-local/task-artifacts/`；持久作品由资产服务写入 `.project-local/projects/`。以根 `.project/paths.json` / `PROJECT_LOCAL_ROOT` 解析结果为准
- `80-evidence/` 和 `.hermes/` 是历史位置，不作为新任务输出根；本次路径说明不授权迁移或删除旧数据
- 不访问 `E:\`；不触碰共享运行时状态
- 进程隔离：Photoshop 以独立进程运行（脚本宿主），不修改宿主配置

## 取证（E3 恢复条件）

1. 绑定当前代码/适配器版本、宿主版本、OS、fixture hash、授权与产物 hash
2. 真实 brief 到原生可编辑 PSD；保存关闭重开，读回文本、图层、蒙版和对象身份
3. 验证修改、失败恢复/回滚并留下动作与回执；仅有退出码、截图或一次 PSD 导出不构成 E3
4. 按根 AGENTS 的证据等级及 Human Gate 验收；本页不替代独立质量/rights/production/release 批准
