# Lite / Launcher / MCP Console 边界裁决

> 只读审计 / 2026-09-29 / current main `010f6a57610214fa41651861e00319f88a2f49a4`。本文是审计与候选方案，不是新 Authority，也不是第二份可编辑任务账本。历史完整性：**未完成**；Windows 实机复测：**本轮未执行**。


| 层 | Authority | 允许职责 | UI深度 | 禁止越界 |
| --- | --- | --- | --- | --- |
| 产品工作台入口 | DESIGN-LAB | 同一个项目/任务/证据模型的Lite模式 | 产品搜索、最近项目、下一设计动作 | 不建立第二runtime/账本 |
| Host Launcher | DESIGN-LAB局部入口 | 打开用户已配置设计软件/项目 | 版本/路径/缺失状态；用户选定宿主 | 不静默安装/改全局配置；不控制所有客户端 |
| Capability Browser | DESIGN-LAB | 按域/宿主/模型筛选真实能力 | supported+evidence+rights+requirements | 不把历史候选全显示为可用 |
| Project / Brief / Asset UI | DESIGN-LAB | 正式产品核心 | 版本、引用、授权、项目作用域 | 不跨项目泄露资产 |
| Host Adapter状态 | DESIGN-LAB | 健康、权限、版本、协议、readback | 设计任务恢复/取消/局部rollback | 不将进程running等同qualified |
| Model / Tool capability状态 | DESIGN-LAB | 设计参数、能力范围、输入输出、资格 | 模型hash、资源需求、fallback | 不做通用模型网关或全机模型管理 |
| MCP / Adapter diagnostics | DESIGN-LAB局部；全局归WORK | 设计端点schema、连接、超时、脱敏日志 | 选定设计工具试调用、能力失效解释 | 全局MCP注册/客户端插件状态/credentials归WORK |
| DESIGN-domain workflow | DESIGN-LAB | Brief→设计→Jury→preflight→handoff | 设计任务依赖与人工gate | 不写通用Agent调度器 |
| 外部workflow coordination | WORK-LAB | 外部请求/结果契约 | 显式项目请求、status与结果ref | DL不接管WORK持久配置；WORK不裁决设计质量 |

## 推荐信息架构

“项目”作为主入口；项目内部依次呈现 Brief / References、Directions / Design System、Design Plan、Runs、Review / Preflight、Deliveries。另设“能力与宿主”页，容纳Launcher、资格与诊断。Lite是少导航、少默认复杂度的同一工作台，不是简化数据模型。高级诊断按需展开，默认首页不充满Agent术语。

设计task cancel与host恢复属于DL；编辑外部client全局plugin state、自动选跨项目Agent、全局credentials属于WORK。standalone-first指无WORK/AAOS也可完成设计链，不意味着禁止轻量UI或可选宿主。Open Design可出现在Launcher中，但其用户级状态管理接口由WORK承担。

## Owner Decision Needed

1. B04/B07/后续VI的唯一视觉优先级与目标密度；提供并排候选后裁决。
2. 若需要原生桌面特性，批准具体ADR及可测收益后再选壳；当前无需阻塞Web增量。
3. 受限制模型/工具许可是否适用于实际使用地点和商业用途；未明确者保留BLOCKED。
4. 首个真实验收项目及可授权输入，独立专业接受人；M1既定双Adobe条件若要变化须明确变更。

单账本、三项目边界、非第二画布已由Authority决定，不重开投票。raster资产扩展到源文件/视频/3D需明确格式、体积、路径与导入契约，不应以“统一资产”名义直接解除所有限制。
