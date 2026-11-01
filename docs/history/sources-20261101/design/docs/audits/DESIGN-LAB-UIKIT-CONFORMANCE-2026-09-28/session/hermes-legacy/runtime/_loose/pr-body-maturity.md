## 范围

按 `docs/research/full-maturity-audit-2026-09-19.md`（本次一并入库的审计基线）执行 **Batch A + Batch E（P1-C/D/E/F）**。

10 个 commit，`origin/main`(`cb2163a`)..`fe3ba27`。

## 已闭环

**P0（Batch A）**
- P0-01/02/03/04/05/07：方向单选不变量（事务内原子取消）、无 chosen 时 readback 返回 null、未 chosen 禁止 bind、`constraints` 对称序列化、Reference 资产校验（存在性/归属/shape/去重）、wheel force-include + catalog 双路解析
- P0-05 前端：Workbench Reference 选择器 + strict-TS 重建 bundle
- P0-06：契约回归 15→18（真实 PNG 导入 helper + DB 态断言）
- P0-08：`workbench-browser-e2e` 专属 job + `playwright` 钉版 + no-skip 强制
- **P0-D**：`active_binding` 严格跟随当前 chosen 方向（切选后归 null）
- **P0-A+**：新增迁移 v2 —— `design_direction(brief_id) WHERE chosen=1 AND superseded_by IS NULL` 部分唯一索引；迁移 precheck 对现存重复 chosen **fail-closed** 并列出 brief
- **P0-I**：E 阶梯对齐 AUTHORITY R2（E2/E3/E4/E5 语义），机器枚举 `capabilityStates` 未动
- **P0-G**：浏览器 E2 证据 JSON + 失败截图 + CI artifact 上传（固定 SHA、`if-no-files-found: error`）
- **P0-H**：wheel 隔离安装态验证（全新 venv + `python -I` + 离线依赖拷贝 + 完整纵切，catalog 非空证明打包资源生效）

**P1（Batch E）**
- P1-C：`reports/current/**` 加显式 provenance（projection/subjectSha/fresh/generatedBy），生成物在当前输入上重生成
- P1-D：`AUTHORITY.md` §15 将已落地 P0 逐项标记 `CLOSED_WITH_REGRESSION_GUARD` + 精确证据（含 gh 读回的 7 项 main required checks），防 TaskPack 重复派工
- P1-E：`authority-index.json` 清除两条已不成立的 `currentButDrifted`
- P1-F：`LANGUAGE-POLICY.md` §4 同步 pnpm workspace 现实
- R2 byte-pin 按 AUTHORITY §17 重配（owner intent/reason/superseded/impact 写在表旁）

## 验证证据（实测）

```
test_design_layer_http.py            Ran 18 tests  OK
test_workbench_design_layer_e2e.py   Ran 2 tests   OK（真实 Chromium）
verify_design_lab.py                 VERIFY_DESIGN_LAB=OK total=49 failed=0
  verify_product_manifest_v3.py      OK total=493 failed=0
  verify_capability_evidence_v4.py   PASS
  open_design_host_adapter           OK total=549 failed=0
verify_top_level_authority.py        TOP_AUTHORITY_GATE=PASS checks=10 failed=none
generate_current_reports.py --check  CURRENT_REPORTS=PASS mode=check scope=bound-input-integrity
wheel_packaging_smoke.py             C02/C03/C04 全 PASS（隔离 venv + python -I 纵切）
gh branch protection                 7 required checks（含 Authority gate + Workbench strict-TS gate）
```

> 说明：`reports/current` 的 rebind 有独立 guard（`generate_current_reports.py --check`），不在 CI 四门禁内（CI 跑 `verify_design_lab` / `verify_product_manifest_v3` / `run_python_tests` / `verify_top_level_authority`）。

## 未完成（保持 OPEN，不做假闭环）

- **P1-B** recorded vs effective evidence 分离（规格见交接文档 §5，可直接执行）
- **P1-A** 版本沿革/取代血缘（Batch F，需先 ADR）
- Batch F 其余：release-preflight、Host E3 预置脚手架
- DesignSystem → DesignIR → 可编辑产物链路；真实 Host E3 / 人工 E4（owner 明确排除实操环节）

## 交接

`docs/handoffs/DESIGN-LAB-P0-P1-MATURITY-HANDOFF-2026-09-20.md` —— 含逐项证据、未完成项的可执行规格，以及本轮并行子代理的实测教训（3 个 429 限流改主线执行；1 个子代理虚假完成 → 子代理自报必须回readback 取证）。
