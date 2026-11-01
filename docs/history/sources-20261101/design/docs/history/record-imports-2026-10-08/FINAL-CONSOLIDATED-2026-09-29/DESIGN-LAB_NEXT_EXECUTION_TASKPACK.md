# 后续执行任务包（候选，未升格）

> 只读审计 / 2026-09-29 / current main `010f6a57610214fa41651861e00319f88a2f49a4`。本文是审计与候选方案，不是新 Authority，也不是第二份可编辑任务账本。历史完整性：**未完成**；Windows 实机复测：**本轮未执行**。

## 授权与调度

本轮只读，本文件不授权修改/commit/push/merge/安装。下一会话由用户明确指令启动实施，再读取LIVE main/PR/protection与Authority。候选CAND编号仅供本报告引用；执行必须挂接现有DL-R5任务，不创造新的可编辑实时ledger。不要重做已实现项目CRUD、bundle create/content、DTCG转换器或Bundles查询。


| 候选ID | 挂接 | 交付 | 实现边界 | 验收 | rollback |
| --- | --- | --- | --- | --- | --- |
| CAND-01 | DL-R5-001/023 | 消除下位漂移 | 对齐E0–E5描述；修6个registry target并验证目标hash；计数按JSON生成 | Authority不变、旧链接有迁移记录、全门通过 | 回退文档/索引提交 |
| CAND-02 | DL-R5-005/010 | Bundle list route+UI | 复用Bundles；DB other+bundle-%；响应design-bundle；项目隔离/分页/排序/空/失败 | route集成测试+UI真实服务；不动已有create/content | 撤route/UI入口，DB不损坏 |
| CAND-03 | DL-R5-005/010 | Token版本闭环 | 复用DTCG；编辑、校验、保存冲突、diff、publish/rollback | 重启持久、历史可恢复、schema往返 | 退回旧版本，保留审计记录 |
| CAND-04 | DL-R5-010 | 商业组件/状态收敛 | 10控件当前实现/SWC/WebAwesome比较；CSP/IIFE/wheel/IME/a11y | 证据表+明确视觉Owner裁决；不先换框架 | featureflag退原组件 |
| CAND-05 | DL-R5-004/006/007/010 | Lite能力与Launcher | 设计宿主路径/版本/资格、任务状态/取消ACK、MCP局部诊断 | 无WORK/AAOS仍可用；无全局状态写入 | 禁用适配入口保留项目 |
| CAND-06 | DL-R5-011/012/013 | 真实Adobe对象闭环 | 授权Brief/参考→IR→创建→2次patch→readback→重开→rollback | exactSHA、host版本、before/after、源文件、对象diff、失败恢复 | 隔离项目和before副本 |
| CAND-07 | DL-R5-014/005 | 专业质量与交付 | 24轴分域rubric+rights/font/link/preflight+human gate；导出BOM/provenance | 硬失败不可平均；独立接受E4；可编辑交付重开 | 撤交付资格，保留问题和产物 |
| CAND-08 | DL-R5-003/009/015 | 可重复研究版 | 安装/升级/卸载/离线/错误恢复；当前CIartifact下载hash；report freshness | 所需M1条件全部满足才宣告；E5需发布可复跑 | 上一包可恢复，项目格式迁移可逆 |
| CAND-09 | DL-R5-008/018 | 可选生成资格 | 先Comfy真实模型10次、再H3分组件；许可/硬件不满足BLOCKED | 取消/断连/资源基准与独立质量对比；无默认安装 | 外部provider/手工素材 |
| CAND-10 | DL-R5-023 | 历史缺口与33语义diff | 恢复原始7个唯一缺失内容+9/28指定原件；逐条比较33演进文件 | 原始hash、source-qualified需求、状态更新 | 保留旧证据，只追加裁决 |

## 依赖与最短路径

CAND-01与02先消除错误前提及不可达功能；03/04/05按独立模块推进；06依赖授权Windows设计环境；07接06真实产物；08只在既定M1门槛齐备后发布。09不阻塞不依赖生成模型的专业闭环。10持续完善历史，但不可借未恢复材料重写Authority。

## 每包回报模板

记录 baseline/final SHA、实际修改路径、当前任务ID、implementation/unit/host_live/delivery四轴、E等级及范围、运行环境、输入授权、artifact SHA256、未完成/Deferred/Blocked/Owner决定、回滚实测。PR前查精确required checks，advisory失败不能冒充required通过或失败。不要用更新时间替代test_run时间。

## 成功标准

个人用户能独立启动工作台，建立一个真实项目，选择已有宿主，完成两次可控修正，知道质量和权利问题在哪里，拿到可继续编辑的源文件与生产说明，并能在失败后恢复。达到这个标准后再扩大域和模型数量。
