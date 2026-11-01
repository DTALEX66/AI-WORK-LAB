# OPEN-DESIGN-Assistance 唯一权威 V4.1 总任务包

版本：`4.1.0-authoritative`  
基线日期：`2026-08-08`  
目标仓库：`DTALEX66/OPEN-DESIGN-Assistance`  
Windows 本地目标：`D:\All projects\OPEN-DESIGN-Assistance`  
唯一执行入口：`HERMES`  

## 本包是什么

这是在当前远端仓库、MiniGame 最终迁移结果、V2/V2.1 开源资料、V3 完整任务包、V4.0 总包，以及 2026-08-08 云端偏航审计基础上形成的唯一后续任务入口。

V4.1 原位升级 V4.0，并保留同一权威任务包身份。最新云端观察基线为 `main@d053a9b7feb966a0dedcd63ebf51356787661da8`；该 SHA 只用于建立审计起点，HERMES 启动时必须重新读取。

本包自生效起：

- 替代所有旧的活动任务入口；
- 旧 V2/V2.1/V3/V4.0 文件只作为继承证据与历史参考；
- 禁止机械重跑旧 90 张任务卡；
- 必须先建立继承矩阵，再只执行净缺口；
- 必须先完成 `ODA4-0110…0118` 云端事实纠偏，随后立即进入 Phase 04/05；
- 纠偏完成后，除阻断性修复外，不得继续以文档、治理、CI 或 MiniGame 工作替代职业设计能力实现；
- 不授权自动 commit、push、PR、merge、ruleset、tag 或 release。

## 最终定位

> 以 Open Design 为主入口，模型中立、风格中立、领域中立、工具中立、权利安全的专业设计智能与视觉质量平台。

Open Design 继续拥有 Studio/画布、Agent 启动、插件运行、Artifact、预览与导出；本仓库只负责专业设计方法、Domain Pack、视觉质量、来源权利、生产预检、可编辑交付、Benchmark 与能力证据。

## 首次使用

在本任务包目录运行：

```powershell
python .\scripts\verify_taskpack.py
.\RUN_FIRST.ps1
```

以上命令只校验任务包并显示启动信息，不修改目标仓库。

随后把 `01_MASTER_HERMES_TASKPACK.md` 完整交给 HERMES。HERMES 必须读取 `tasks/phases.json` 与 `tasks/task-cards.json`，从 `ODA4-0001` 开始执行。

同时必须读取 `02_CLOUD_DRIFT_AUDIT_20260808.md`。它记录 V4.1 的事实纠偏原因、当前偏航判断和强制转向规则。

## 默认执行模式

```json
{
  "mode": "audit_plan_and_staging",
  "single_writer": true,
  "windows_native_first": true,
  "live_apply": false,
  "github_write": false,
  "third_party_default": "quarantine",
  "evidence_root": ".hermes/task-artifacts/open-design-v4/"
}
```

## 绝对禁止

- 不访问、枚举或修改 `E:\`；
- 不读取或输出凭据、OAuth、API Key、Cookie、SSH 私钥、token、认证数据库；
- 不默认写入用户 Home、Codex Home、Open Design 私有配置或整个 `D:\All projects`；
- 不在未知脏工作区或存在其他 writer 时写入；
- 不把 synthetic、静态校验或文件存在冒充 E3 真实运行；
- 不把大师姓名、受保护作品或品牌资产直接变成生成滤镜；
- 不将 MiniGame 移回 WORK-LAB；
- 不让 MiniGame 的 HUD/暗色视觉成为平台默认审美；
- 不继续扩张 MiniGame 的玩法、广告、商业化、上架或平台产品逻辑；
- 不把 adapter 声明、静态文件、测试数量或 synthetic 结果冒充真实能力；
- 未经单独授权不进行任何远端写操作。

## 正确完成状态

默认执行最终只能停在：

- `READY_FOR_USER_APPROVAL`：本地冻结树及证据已完成，等待用户授权远端动作；或
- `BLOCKED`：存在许可、凭据、运行时、环境或证据阻断。

没有 E3 不得称运行可用；没有 E4 不得称发布完成；没有 E5 不得称商业验证完成。
