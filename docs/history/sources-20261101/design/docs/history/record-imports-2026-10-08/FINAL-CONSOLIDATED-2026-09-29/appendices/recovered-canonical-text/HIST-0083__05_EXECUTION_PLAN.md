# 实施顺序与关键路径

## Wave A：可信底座

Phase 0–3。先完成基线、隔离合并、定位统一、旧插件兼容和统一 verifier。此阶段未完成前，不扩展更多风格和大师名单。

## Wave B：最小完整商业闭环

Phase 4–6。打通 `brand-campaign-360 + visual-quality-core + master/style engine`，用一个品牌任务验证状态、方向选择、评审、精修、预检和交付。

## Wave C：领域扩展

Phase 7–8。依次建设平面、UI、空间、包装、编辑、动效、3D、产品视觉和插画/IP。每个领域必须同时拥有 Scenario、Schema、Rubric、Profile、Case，不允许只新增 Prompt。

## Wave D：证明有效

Phase 9–11。建立 no-skill / v1 / v3 对照、视觉评审校准、真实案例和商业证据。质量没有显著提升的 Skill 不晋升。

## Wave E：生产硬化

Phase 12–15。完成供应链、CI、索引、文档、冻结树、独立 Codex 复审和最终审批。

## 严格关键路径

```text
OD-0001 → OD-0101 → OD-0104 → OD-0202 → OD-0309
→ OD-0401 → OD-0403 → OD-0501 → OD-0605
→ OD-0701/02/03 → OD-0806 → OD-0903
→ OD-1002 → OD-1003 → OD-1101...
→ OD-1301 → OD-1501 → OD-1502 → OD-1504
```

## 每个任务的执行模板

1. 读取任务卡、依赖和 allowed paths；
2. 记录当前 HEAD/tree/status；
3. 先增加测试或 fixture；
4. 运行定向测试确认失败或缺口；
5. 由唯一 writer 实现；
6. 定向测试通过；
7. 运行当前阶段 gate；
8. 写入证据和状态；
9. 检查 Git diff 范围；
10. 再进入下一个任务。
