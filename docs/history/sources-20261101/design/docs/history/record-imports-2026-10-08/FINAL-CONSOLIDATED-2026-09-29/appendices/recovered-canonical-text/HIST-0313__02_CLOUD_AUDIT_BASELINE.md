# 云端审计基线（2026-08-10）

## 已核验事实

- 仓库：`DTALEX66/OPEN-DESIGN-Assistance`
- 默认分支：`main`
- 基线 HEAD：`4ae0981b1d75ac1d20cac3a231b7e157854a4fb9`
- `main` 与 `migration/work-lab-minigame-cutover-20260807` 当时指向同一 SHA。
- `minigame-runtime/` 已进入云端 `main`。
- 无开放 PR。
- 最新产品相关提交之后只有安全/CI 修正和审计报告；没有新增完整专业能力纵切。
- 当前 HEAD 没有精确 SHA CI；最近成功 Canonical V4 为 `5744b3fa`。

## 仓库形态

- 约 752 个 tracked files；`opendesign-assistance` 主要由 Markdown、JSON、Python 构成。
- 没有独立前端应用、设计工作台、完整 API 后端或数据库运行层；这符合“不复制 Open Design 前端”的边界，但专业能力运行层尚未形成。
- 三个 Bundle 目录存在，但未完成真实 Open Design 注册闭环。
- 只有一个旧 `minigame-design` Domain Pack，且不满足 V2 十部分 manifest 合同。
- 12 张 evidence card 全部为 `E0/not-run`。
- 112 个通用来源、22 个视觉来源已登记；497 条大师记录、77 张方法卡仍需来源和成熟度治理。

## 已确认 P0 缺陷

1. 兼容矩阵仍含 Open Design 0.13.0，而 canonical 文档使用 0.18.1。
2. README 使用不存在的 `--permission-root` 参数。
3. Windows 配置脚本宣称安全边界，但 apply 路径仍会修改 Open Design 私有配置和启动器。
4. clean-tree workflow 只打印数量，不会因脏树失败。
5. workflow path filter 漏掉部分会改变 canonical 状态的文件，因此当前 HEAD 无 exact-SHA 运行。
6. 插件、Bundle、Domain Pack 的人工计数与真实目录不一致。
7. Figma、Penpot、browser 等适配器把声明状态写成 available，缺少版本、任务和 Artifact 证据。
8. 缺少 `capability-evidence-index.json`。
9. 许可证 Gate 尚未覆盖完整 REUSE、SBOM、第三方 BOM 与二进制 sidecar。

## 执行时重核

本文件是时间点基线，不是永久事实。执行 `V42-0001` 时必须重新核验；HEAD、分支、PR 或 CI 有变化则输出 delta audit 后再写入。

