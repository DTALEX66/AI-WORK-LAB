# 全局（所有软件）配置审计 —— 纠正版（2026-08-23）

> 纠正：全局 = 一套规则适配部署到【所有软件】（Hermes/Codex/DSH/CC Switch/OpenHuman/Open Design），
> 不是单指 Hermes。重新审计各软件的全局配置/技能开销。

## 1. 各软件全局配置实测

| 软件 | 全局技能/配置 | 评估 |
|---|---|---|
| Hermes | 82 skills / 866KB（含大量 macOS 技能）| 🔴 膨胀 |
| Codex | **328 skills/prompts**（.codex 根目录）| 🔴 膨胀（比 Hermes 还多）|
| DSH | settings 0.4KB + 15 插件 | 🟢 轻量 |
| CC Switch | db 0KB（已退役）| 🟢 退役 |
| OpenHuman | 19 文件 | 🟡 中等 |
| Open Design | 76 文件 = 程序 dll（Electron 运行时，非配置）| 🟢 不算开销 |
| WORK-LAB 规则 | config-ownership 10.5KB + registry 9.6KB + AGENTS.md | 🟢 规则定义 |

## 2. 核心结论（纠正）

### 全局负担 = Hermes 82 skills + Codex 328 skills（两个软件技能膨胀）

```
不是 Hermes 单独——Codex 更严重（328 个技能/提示文件）
共同根因：技能/提示大量维护，但执行时不先调用（直接开干）
→ 白维护 + 零调用 = 纯负担
```

### 一套规则部署现状

```
WORK-LAB 规则定义（config-ownership + registry + AGENTS.md）✅ 有
但各软件自己的全局技能/配置各自膨胀、不一致、执行不调用
→ 缺：①技能精简 ②强制先查技能机制 ③各软件全局配置对齐
```

## 3. 精简建议（全局 = 所有软件）

| 软件 | 动作 |
|---|---|
| Hermes | 82 → ~25 核心（删 macOS/无关，归档 40-knowledge）|
| Codex | 328 → ~20 核心（确认哪些实际用，其余归档）|
| DSH | 保持（已轻量）|
| OpenHuman/Open Design | 保持（程序文件非配置）|
| 所有软件 | 加"先查技能再执行"强制步骤（技能白维护的根治）|

## 4. 状态

- 纠正后的全局审计（所有软件）
- 待用户选择执行项