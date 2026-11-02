# OPEN-DESIGN-Assistance 完整深化优化任务包 v3.0

生成日期：2026-08-05

目标仓库：`D:\All projects\OPEN-DESIGN-Assistance`  
GitHub：`DTALEX66/OPEN-DESIGN-Assistance`  
执行链路：`HERMES + Open Design + Codex + GitHub`

## 这个包是什么

这是对前述全部对话、仓库审计、V2 全网吸收、V2.1 视觉质感与大师方法增强的统一收束。它同时包含：

1. **完整 HERMES 总任务书**；
2. **90 个结构化任务卡**；
3. **16 个实施阶段与依赖顺序**；
4. **V2 + V2.1 合并后的 199 文件统一 Overlay**；
5. 风险、证据、审批、复审和回滚 Schema；
6. Windows 原生安全应用脚本；
7. 原始 V2/V2.1 包及来源追踪；
8. 最终验收、质量 8+、商业交付和 GitHub 发布合同。

## 首次使用

先在本任务包目录运行：

```powershell
python scripts\verify_complete_taskpack.py
python scripts\apply_unified_overlay.py "D:\All projects\OPEN-DESIGN-Assistance" --plan
```

以上命令只验证和生成计划，不修改目标仓库。

随后把 `01_MASTER_HERMES_TASKPACK.md` 完整交给 HERMES。HERMES 必须从 Phase 0 开始，不得跳过基线、并发检查、证据等级和隔离 staging。

## 默认禁止

- 不自动覆盖目标仓库现有不同内容；
- 不删除任何现有文件；
- 不访问或修改 `E:\`；
- 不读取凭据、OAuth、API Key、Cookie 或私有认证文件；
- 不自动 commit、push、创建 PR、修改 Ruleset 或发布；
- 不把静态文件存在宣称为 Open Design 运行时可用；
- 不把大师姓名作为最终图像/设计生成滤镜；
- 不整包 vendoring 未审查的第三方仓库、模型权重、字体或素材。
