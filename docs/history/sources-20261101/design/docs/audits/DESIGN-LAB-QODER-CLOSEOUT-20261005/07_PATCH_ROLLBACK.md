# 07 — C5 Readback / Patch / Recovery / Rollback

状态：**`PARTIAL`（E1 合同 + E2 受控运行时；无本轮宿主 E3）**。
对应 `DL-R5-004 / 011 / 012 / 013 / 014`。

## 本轮真实推进的部分

`plan_to_rir` 把分析产物接进**已经具备** patch/readback 语义的那套对象模型，
并保持 `object_id` 不变（`04_DESIGN_IR_EVIDENCE.md` 有测试钉住）。
这意味着一旦宿主跑通，patch 定位不需要新的 id 体系。

## 既有链路（复用清单，未重写）

| 环节 | 实现 | 合同要点 |
|---|---|---|
| execute → receipt | `src/design_lab/runtime/job_store.py` 尝试态词表 + `TERMINAL` | `OUTCOME_UNKNOWN` 归「待审」不计失败 |
| host readback | `adobe_job` / `photoshop_com` digest 封条 + `%PDF`/`8BPS`/PNG 头校验 | 读回失败不得包装成 SUCCESS |
| object-level patch | `native_patch_plan.prepare_patch` | 要求先有 **RECEIPTED** attempt；绑定 baseline/checkpoint/input hash + 幂等键；Illustrator 支持 text/path（拓扑保持），Photoshop 支持 text/move |
| version/asset | `asset/version` + `/api/projects/:id/bundles` | 交付包 sha256 + byte_size fail-closed 核对 |
| rollback | `native_recovery` / lock & restore 路径（`test_native_recovery_lock.py`） | 单元级已覆盖 |

## 本轮**没有**做到的（必须如实列出）

1. **两次局部修改**（任务书 C5.1）：未执行。需要宿主，见 `05/06`。
2. **失败矩阵**（C5.2：host unavailable / wrong document / stale version /
   missing asset / invalid object id / cancel / partial execution / readback mismatch）：
   仅单元级覆盖，**没有**本轮真实宿主下的失败观测。
3. **rollback 后再读回**（C5.3）：同上，未在本轮真实宿主里执行。
4. Illustrator patch 目前只覆盖 `text`/`path`，Photoshop 只覆盖 `text`/`move`；
   **mask / raster 的局部 patch 不存在**，不能宣称“对象级 patch 全覆盖”。
5. 文本像素局部性（pixel-locality）在历史记录里是 FAILED，未被本轮推翻。

## 结论

`execute → receipt → readback → compare → patch → readback → version` 这条链
**合同完整、代码存在、单元与受控层可跑**，但缺宿主 E3 实测；
因此 C5 记 `PARTIAL`，不记 `DONE_E3`。
