# Rights Decision（DL-TP-R0-006，2026-09-04）

- 项目用途：**PERSONAL_RESEARCH_NONCOMMERCIAL**（个人研究、非商业）
- 状态：ACTIVE｜全局继承

## 组件继承

- 所有模型/素材/软件组件默认继承 PERSONAL_RESEARCH_NONCOMMERCIAL
- 商业交付、收费服务、对外托管、受限模型/素材再分发 → **forbidden**

## 记录范围

- 素材/人物/商标/声音、模型权重、输出披露、再分发限制均须记录（SourceRecord/sidecar）

## H3 特别门（minimax-h3-local）

- **0.1 禁止向第三方分发 H3 Works**（权重、派生模型、修改件），无论是否收费
- 输出仅可在适用地域内分享；公开样例必须含**可见 AI 生成标识**（不能只在 Receipt/metadata）
- 地域门：操作者须声明真实下载/部署/使用/展示地域，保存适用许可 hash + AUP 版本/日期 + 书面授权引用
- 不得用 IP/账号/缓存位置猜测地域
- 进入排除地域且无有效书面授权 → `minimax-h3-local` = **BLOCKED_BY_LICENSE**
- 覆盖：权重、工作流、输出、备份、移动硬盘、远程桌面显示、导出、交付

## Fail-closed 条件

- 商业交付/托管、H3 Works 第三方分发 → forbidden
- 向排除地域分享/交付输出、地域/授权未知、设备跨境、许可/AUP hash 漂移、到期或权限撤销 → fail-closed
- 公开输出缺可见 AI 标识 → 阻断
- 变更用途 → 需新 ADR

## 证据

- RightsDecision（本文件）、territory declaration、license/AUP hash、authorization ref、sidecar、跨境/到期/撤权拒绝测试
