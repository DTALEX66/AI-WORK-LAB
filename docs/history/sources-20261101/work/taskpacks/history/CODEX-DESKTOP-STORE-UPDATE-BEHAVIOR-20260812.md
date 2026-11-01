# Codex Desktop Store-Update Behavior — Official Findings（2026-08-12）

> 结论归档：用户反馈"Codex 频繁要求重新登录 + 桌面外观/沙盒重置"，经官网
> 查证（learn.chatgpt.com Codex/ChatGPT 桌面版文档）+ 本机证据，确认根因与
> 归属。本文件为 tracked 归档，供后续排查引用，避免重复诊断。

## 1. 根因

**Codex Desktop = MS Store 商店版（OpenAI.Codex，MSIX）**，Windows 官方唯一
安装渠道（`winget --id 9PLM9XGG6VKS -s msstore`，无独立安装包）。商店版
**个人版自动更新且不可推迟**（Enterprise 才有更新管理，见
[windows-deployment](https://learn.chatgpt.com/docs/enterprise/windows-deployment)）。

"频繁登录 + 外观/沙盒重置" = **商店自动更新（微软机制）** × **OpenAI 应用更新后
本地状态未完整保留（应用侧策略）** 的组合效应。非故障、非商店故障，是官方分发
渠道的固有特性。

## 2. 三层配置行为（结论）

| 配置层 | 商店更新会重置吗 | 依据 |
|---|---|---|
| `~/.codex/config.toml`（用户配置：模型/provider/自定义） | **不会** | 更新只替换 `WindowsApps` 应用目录（MSIX 机制），不碰用户目录 |
| 桌面外观/偏好（主题/布局，`.codex-global-state.json` + `AppData\Local\Packages\OpenAI.Codex_*`） | **可能**（更新后回默认） | 应用状态迁移不保证持久（[Settings](https://learn.chatgpt.com/docs/reference/settings.md) 无持久性承诺） |
| 登录会话（`~/.codex/auth.json` token） | **可能要求重登** | token 在不活跃期过期；官方仅在活跃使用时自动刷新（[Auth](https://learn.chatgpt.com/docs/auth.md)） |

## 3. 关键区分：受管字段消失 ≠ 商店更新

- config.toml 的 overlay 受管字段（approval_policy / sandbox_mode /
  project_doc_max_bytes）消失 = **Codex Desktop 应用运行时重写 config.toml**
  （每次启动/操作），不是商店更新（时间线实测：更新 08-11 19:48，重写 08-12 23:30）。
- 用户字段（如 `model_provider=cc-switch-official`）在重写中被保留，
  丢失的仅是不被应用识别的注释块。

## 4. 缓解（无根治——官方机制）

1. **登录**：保持活跃使用（官方唯一减少频率的办法）；更新后一次性重登。
2. **外观**：更新后重新设置一次（无防重置机制）。
3. **overlay 受管字段**：需要时一条命令恢复
   `python scripts/workflow/sync_codex_global_assets.py apply && verify`
   （会复发，属应用重写行为，非更新）。
4. 个人版无 access token（Enterprise 专属）、无关闭自动更新选项。

## 5. 与本项目的关系

- **五维基线不受影响**：基线覆盖 provider 官方路由/无限额/reasoning，全部正常；
  登录/外观/受管字段属应用状态层，与基线配置无关。
- 排查时不要将"登录/重置"误判为配置漂移（参考 hermes-codex-config-drift：
  所有权分层，先判定层再行动）。

## 6. 社区证据（GitHub openai/codex，2026-08-12 查证）

| Issue | 内容 | 状态 |
|---|---|---|
| [#37927](https://github.com/openai/codex/issues/37927) | **商店更新覆盖 local-projects 空状态并镜像 .bak**——与本机现象完全一致（同版本线 26.803.10989.0，ChatGPT Pro，恢复后两次干净重启保持） | OPEN 未修复 |
| [#38008](https://github.com/openai/codex/issues/38008) | 桌面应用强制 SMS/WhatsApp 验证 | OPEN |
| [#32417](https://github.com/openai/codex/issues/32417) | UI 设置不持久（custom model provider） | OPEN |
| [#36490](https://github.com/openai/codex/issues/36490) | Windows 登录 token_exchange_failed | OPEN |

**判定**：本问题为官方已知 bug（商店更新触发状态覆盖），非个例、非配置漂移。
Windows 无规避渠道（仅商店）；macOS 独立包手动更新基本不涉及。
跟踪：关注 #37927 官方修复。
