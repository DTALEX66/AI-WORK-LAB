# DESIGN-LAB UI 商业级 Workbench — GOLDEN_FLOWS（黄金流）
任务包：DESIGN-LAB_UI_FRONTEND_TASKPACK_20260930 · 分支 feat/ui-commercial-workbench-20260930

两条黄金流。**本轮范围内执行的是流 A 的前端读回层；流 B 的宿主实操
（PS/AI 真实出图）不在本分支执行**（用户范围裁决：不操作宿主自动化任务）。

## 流 A — design-lab 设计 design-lab（纯服务闭环，无宿主）

```
1. 连接本机设计服务（#login → /api/projects 读回）          [既有]
2. 新建项目「DESIGN-LAB 商业级 UI」                          [既有 #create-form]
3. 进入项目详情（#/projects/:id）
   └ 阶段导航：Brief
4. 创建简报（#pd-brief-editor → POST /projects/:id/briefs → 读回 v1）  [W03 既有]
5. 阶段导航：Directions
   └ 新建方向候选（POST /projects/:id/directions → 读回）  [既有]
   └ 选定方向（POST /directions/:id/choose）              [既有]
   └ Inspector 版本环显示 v1 节点（is-chosen 高亮）       [新增]
6. 阶段导航：Design System
   └ 绑定（POST /directions/:id/bind → 活动绑定读回）      [既有]
7. 阶段导航：Production
   └ 提交 native-plan（POST /projects/:id/native-plans）  [既有高级区]
   └ 仪表盘「活跃生产」读回 in_flight 任务                 [新增]
8. 任务完成 → 打包
   └ 仪表盘 + 项目页「最近交付」读回 /bundles              [新增]
   └ 下载交付包（hash fail-closed 核对）                  [既有]
9. 阶段导航：Evidence
   └ 证据绑定链：项目 → brief v1 → 选定方向 → 交付包      [新增]
10. 刷新页面 → 项目上下文保留（recency + hash）           [既有]
```

本轮新增读回点：步骤 5（版本环）、7（活跃生产）、8（最近交付）、9（绑定链）。
失败路径：步骤 4 STALE_REVISION / BRIEF_NOT_FOUND 走 revisionHint 真实文案；
步骤 7 服务不可达显示「未读回」而非 0；步骤 8 hash 不一致 fail-closed 拒收。

## 流 B — 真实商业视觉（宿主实操，不在本分支执行）

```
1-3 同流 A（连接 / 建项目 / 简报）
4. 参考素材导入（#pd-reference-panel 批量导入 + 取消 + 逐条结果）  [W04 既有]
5. 宿主官方入口出图（Illustrator / Photoshop）                    [宿主执行]
6. 原生资产导出 → /projects/:id/native-assets 读回               [既有]
7. 交付包 → 预检（#/preflight 任务 ID）→ 人工验收 → 发布         [既有 + owner 门]
```

边界声明：第 5 步的宿主实操依赖宿主软件官方接入（ADR-001 standalone-first：
DESIGN-LAB 不拥有宿主私有数据库，宿主以官方插件/CLI/MCP 扩展形态接入）。
本分支的 UI 层为第 5-7 步提供**读回与状态标注**（任务台账 / 原生资产 /
交付包 / 预检判定），不代替宿主执行。

## 回归不变量（两条流共用）
- 旧单页工作入口（空 hash）字节不变，迁移完成前可用。
- 所有写入 = 经现有 service → 执行 → receipt → readback（无旁路）。
- 刷新保留项目上下文；失败不弹「保存成功」。
