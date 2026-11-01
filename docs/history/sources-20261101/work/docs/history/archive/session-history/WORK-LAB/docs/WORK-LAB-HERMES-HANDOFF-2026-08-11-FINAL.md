# WORK-LAB HERMES HANDOFF — 2026-08-11 FINAL

> 交接范围：五维运行时基线审计 + Observer 全面修复增强 + CI 升级 + SKILL 吸收。
> 全部已合并至 main，双端一致。本文件为 tracked 交接文档（非运行数据）。

## 1. 交付总账（本日 PR 链，main 均含）

| PR | 内容 | 合并 SHA |
|---|---|---|
| #54 | codex launcher versioned-glob + dashboard freshness 词汇 | `a2c51a3` |
| #57 | revert #56 — Open Design 全局配置归 WORK-LAB MANAGE（两层级边界） | `6ccd7cf` |
| #58 | error-ledger ERR-045（reasoning 降智）/ ERR-046（codex.cmd 死入口） | `431ef93` |
| #59 | actions/checkout v4.2.2 → v7.0.1（Node24，消 deprecation） | `e77c9a3` |
| #60 | Observer 全面修复（freshness 词汇/usage series/治理加载/compact 指标/MINIGAME 移除 + gate 同步 + CURRENT_STATE 新鲜化） | `34f21b6` |
| #61 | SKILL 吸收（update-safety 新建 + github-delivery 增强 exact-SHA 陷阱） | `23baa6f` |

## 2. 五维运行时基线（AGENTS.md 强制章节，已落地）

1. 入口唯一 — Hermes（.lnk→vbs+CLI）/ Codex（bash+cmd wrapper 版本化 glob 一致）/ CC Switch·OpenHuman·Open Design（桌面 .lnk）
2. 桌面可达 — 全部快捷方式目标链 Test-Path 通过
3. 官方标准+用户配置 — config-ownership 合同字段层 preserve_unknown
4. 无阻塞 — skills 8KB/个（<10KB 基线）· guidance 10.6KB · wrapper 无死候选
5. 模型满血 — reasoning_effort=medium（官方默认，live 实测）· CC Switch 官方 provider 无限额（cost_multiplier=1.0）· Codex gpt-5.6-sol 端到端

## 3. Observer 修复明细（#60）

- freshness 词汇统一：canonical 投影输出 UI 词汇（fresh/stale/offline/unknown），修复 UI 永远"未知"
- usage series：分列 token 求和 + observed_at 时间桶（趋势图恢复）
- 治理面板：从真实 repo（CURRENT_STATE/adapter-registry/rules）加载
- compact 指标：任务数取自 summary.tasks（非项目列表长度）
- MINIGAME 残留移除（TRANSFERRED_PROJECT_IDS 仅 open-design）
- runtime-convergence gate 同步新契约（20/20 全绿）

## 4. SKILL 吸收（#61）

- 新建 `workflow-assistance-update-safety`：四层证据/所有权分层/并行会话竞态/managed-block 恢复（吸收 agent-update-safety + hermes-codex-config-drift）
- 增强 `workflow-assistance-github-delivery`：CURRENT_STATE squash 陷阱、merge API 405、语义 gate ID、SKIP 信任（吸收 exact-sha-ci-delivery）
- Codex live：14 个受管 skills（apply 已同步本机，verify PASS issues=[]）

## 5. 当前状态

```text
main:        23baa6f（本地 == 远端 == origin/main，工作树 clean）
CI:          #59/#60/#61 全绿 · main 精确 SHA success
Codex overlay: 14 skills · verify PASS · issues=[]
Hermes live:   reasoning_effort=medium（live 实测）· bin 同步 · Hermes 受管 skills 在其自有命名空间（software-development 等），与 Codex 侧 12 个 workflow-assistance-* 分开
运行时:        sidecar 动态端口 + dashboard :6522（需重启时重新拉起）
error-ledger:  46 条（9 分类）verify PASS
CC Switch:    127.0.0.1:15721 正常（codex-official 官方路由）
```

## 6. 续接任务（待用户/后续）

- [ ] WL3-820 正式 release 批准（批准包已就绪）
- [ ] `v0.1.0-alpha.1` 标签指向清理前提交（已有 `v0.1.0-native-observer` 新基线）
- [ ] CLO TaskPack（CLO-CODEX-EXECUTION-RELIABILITY-20260810）执行回读
- [ ] 并行会话「设计增强8.7」建议专注 DESIGN-LAB，避免双写 WORK-LAB 工作树
- [ ] 机器重启后：sidecar + dashboard 需重新拉起（命令见 Observer AGENTS.md）

## 7. 边界与安全（始终有效）

- 禁读/禁打印凭据、auth 存储、会话库；值一律 `[REDACTED]`
- 禁 `E:\`；禁 reset --hard / clean / force-push（重写历史需单次授权）
- 只读观测模块：Observer 零写入，Telemetry Ledger 唯一
- Open Design：非设计全局配置 MANAGE / 设计能力配置 IGNORE
- 并行会话竞态：写前复验分支+HEAD，写后 re-grep 标志

## 2026-08-12 增补（本日续接成果）

### 已合并 PR（main 均含，本地=远端）

| PR | 内容 | SHA |
|---|---|---|
| #63 | 本机配置声称修正（reasoning_effort=low、Codex 12 skills） | 6777928 |
| #64 | managed-software-and-assets 漂移修正 | ad9e20c |
| #65 | SKILL 吸收（observer-delivery 新建 + 3 技能合并，12→13） | 3e66b1f |
| #66 | 文档整理 + TASKPACK_SUMMARY 更新 + CURRENT_STATE | 6eaf6b3 |
| #67 | verification-hardening skill（幻觉核验/升级安全网/审批自适应） | 400d82d |

### 本机部署（不入库）

- hermes-upgrade-watch.py → Hermes post_api_request hook（版本变化自动备份 config.yaml+SOUL.md，实测触发成功；首次使用需批准）
- Codex network_access=true（Open Design 上传 git push；备份 config.toml.bak-network-fix-20260812105059；端到端验证待 Codex 重启后）
- Open Design 桌面双入口已修（单入口）；.bat CODEX_BIN 更新至 8e8bf206

### 状态

- skills: 14（含 verification-hardening）
- error-ledger: 48 条（9 分类）verify PASS
- 服务: sidecar :3525 + dashboard :6522 LIVE

## 2026-08-12 增补 2（数据外溢治理与 E 盘保护）

### 数据外溢治理（C 盘/盘根）

- C 盘 92% 根因：第三方软件数据（Photoshop Temp 13.2G、金山 7.7G、腾讯 4.1G、
  字体 4.1G、Open Design 2.5G、Hermes 运行时 5.3G），非本项目外溢。
- 盘根残留清理：C:	emp、C:\d、D:\d、D:\c、D:\cache、D:、D:\.appdata
  共 7 个旧工作流/路径拼接残留已清。
- 保留（软件活动）：C:\AITEMP + D:\AITEMP（Adobe Illustrator 2023 AIRobin.exe
  暂存盘）、C:	mp + D:	mp（Open Design od-skill 标记）。
- **关键经验：agent 边界规则约束代理行为，不约束第三方软件本体**。Adobe/Open
  Design 写盘根是软件自身策略，需软件配置改（如 AI 暂存盘、Open Design 临时目录），
  不是边界规则失效。

### E 盘保护补全（Hermes 侧）

- Hermes 全局规则机制研究结论：
  - SOUL.md（HERMES_HOME）→ 所有会话始终加载 ✅
  - .hermes.md / AGENTS.md → 仅从项目 cwd 向上加载（HERMES_HOME 的不生效）
- 已落地：SOUL.md 追加全局安全规则（E 盘无明确授权禁止访问、项目数据边界、
  凭据纪律、破坏性操作确认、副作用逐项授权），所有会话生效。
- Codex 侧 E 盘规则（AGENTS.md + config.toml writable_roots 排除）验证完好。

### 双端一致

- HEAD = 1723efb（PR #68 日结）· 工作树干净 · error-ledger 48 条 · Ledger 19 条
