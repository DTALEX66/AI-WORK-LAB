# DSH 第三方插件评估（2026-08-17）

> 来源：awesome-dsh-plugin（7.5k⭐ 官方社区目录）+ GitHub 搜索。评估对 WORK-LAB（Control Plane）的适配价值。

## 1. 生态概况

| 项目 | Stars | 说明 |
|---|---|---|
| awesome-dsh-plugin | 7,482 | 官方社区插件目录（20+ 分类）|
| deepseek-harness-desktop | 11,473 | DSH 桌面端 |
| open-design | 88,202 | 设计插件（AGENTS.md 已定外部 client 边界）|
| dsh-browser | 246 | Chrome 侧边栏，DSH 操控浏览器 |
| dsh-market | — | DSH 内置插件市场（一键装/升级）|
| dsh-find-plugin | — | agent 帮你找插件 |

## 2. 与 WORK-LAB 最相关的分类与插件

### ⭐ Usage & Billing（60+ 插件）—— 与 Control Tower Token/成本直接相关
这些插件**从 DSH session 日志读精确 token**（不是估算）——可替代 WORK-LAB 的 token 估算路径（原估算器已于 2026-10-25 按本轮删除清单退役，仓库内暂无实现，重装该能力属新建）：
- **Jannchie/dsh-bill**：8000+ 模型实时定价（models.dev + OpenRouter），每调用精确计价，成本归因（tool/model/命令）
- **LeemanCheung/dsh-token-usage**：本地优先四桶 token 观测（session/provider/model/day）
- **SenmuuuuW/dsh-whale-report**：DeepTrace 确定性会话报告（只读，不重写历史）
- **dsh-heatmap / dsh-token-heatmap**：GitHub 风格用量热力图
- **2006spy/dsh-token-billing**：DeepSeek 官方 CNY 定价 + 峰谷自动切换

### 其他相关分类（需进一步看）
- **Workflow & Automation**：任务流/自动化
- **Git & Code Review**：CI/证据
- **Security & Permissions**：治理（Policy）
- **Memory**：Agent 记忆

## 3. 对 WORK-LAB 的适配建议

### A. 立即可用（安装到 DSH）
- **dsh-market**（插件市场）：先装它，之后在 DSH Web GUI 里一键浏览/安装其他插件（最省事）
- **dsh-find-plugin**：让 DSH agent 按需推荐插件

### B. 高价值（Token/成本精确化）
- 选 1-2 个 Usage/Billing 插件装到 DSH（如 dsh-bill 或 LeemanCheung/dsh-token-usage）→ DSH 侧显示精确 token/成本
- **参考其实现**：WORK-LAB 的 token 估算路径可从"估算"升级为"读 DSH session 精确 token"——注意原估算器已在 2026-10-25 退役，因此这是一次新建而非改造（当前 DSH 会话数据已挖掘过，但 token 字段缺失——这些插件证明 DSH session 里有 token 可读，需要正确解析方式）

### C. 边界（不装/谨慎）
- **open-design**（88k⭐）：AGENTS.md 已明确——外部 client，WORK-LAB 管其 USER_GLOBAL 但不采集能力（能力属 DESIGN-LAB）
- 第三方插件**有安全风险**（目录明确警告：插件以你的权限跑代码）——只装高星/审核过的

## 4. 结论

- DSH 插件生态**丰富且活跃**（今天全在更新）
- **最值得**：dsh-market（入口）+ 1 个 Usage/Billing 插件（精确 token）
- **对 WORK-LAB 的战略价值**：证明 DSH session 可读精确 token → token 观测可从估算升级（原估算器已于 2026-10-25 退役，升级即新建；且需用户决定是否安装第三方插件到 DSH）
