# CLOUD AUDIT BRIEF —— bundle 查询层切片（网页 GPT 审计入口）

**用途：** 让**网页 GPT**（无本地文件系统、只能读公开网络）能独立审计本轮改动。
本文件自带全部锚点（exact SHA / blob SHA / PR / run URL / 行号），并明确列出
**可证伪的断言**、**明确未做的部分**与**两处会被误读的红色 CI 记录**。

**仓库：** `github.com/DTALEX66/DESIGN-LAB`（**public**，`private=false`，默认分支 `main`，未归档）

---

## 1. 审计目标 SHA

| 角色 | SHA |
|---|---|
| **本轮最终 main（审计此 SHA）** | `010f6a57610214fa41651861e00319f88a2f49a4` |
| 上一状态（PR #205 后） | `b86c6da84ad94b50ca68c0cef9b85b627c1fbf47` |
| 本轮开始前基线 | `c428136093c5435fc6172ee5c0272062aa7c0628` |

> 按 `/AUTHORITY.md`（`DL-AUTHORITY-2026-09-18-R2`）：**任何云端 GPT 审计必须声明它实际观察到的 exact SHA。**
> 若你读到的 `main` 已不是 `010f6a5…`，请以你读到的 SHA 为准并说明差异。

### 1.0 「main 已前进」——由本文件自身造成，且不影响审计结论

本文件由 **PR #208** 加入。此后**每一次编辑本文件都会再次推进 `main`**，因此本文件
**刻意不声明"当前 main 是哪个 SHA"**——那种句子必然立刻过期。判据永远是 §1.1 的 **blob SHA**：

- 被审计的**四个文件**在 `010f6a5…`（切片落地时的 SHA）与**任何后续 main** 上
  **逐字节相同**（blob SHA 不变，见 §1.1）；
- 这些 blob SHA 是**内容级别**的身份，与 `main` 前进、与提交/合并方式无关；
- 本文件**自身**由 #208 引入，故它在 `010f6a5…` 上**不存在（404）——这是预期，不是缺陷**。

| 事实 | 值 |
|---|---|
| 被审计四个文件的 blob SHA | 见 §1.1（在 `010f6a5…` 与后续 main 上相同） |
| 本文件自身 blob SHA | 随每次编辑变化，**不构成判据**——请以你读到的那一刻为准 |
| 本文件在 `010f6a5…` 上 | **不存在**（由 #208 加入） |

**含义：** 审计内容与 SHA 前进**无关**——在你读到的任何 main 上，对 C1–C8 的判定**必须一致**。
若你在你读到的 SHA 上发现 §1.1 的 blob SHA 不匹配，说明**被审计内容**已被改动，请明确指出。
（你实际观察到的 main SHA 请照 §1 的要求声明；它与 §1.1 的 blob SHA 是两件独立的事。）

> ⚠️ **并发第三方 PR 披露：** 本轮期间存在**另一个非本会话的 PR #207**
> （`codex/github-delivery-docs-20260929`，标题 *fix(ci): scope main artifact proof to main*），
> 处理正是 §4 提到的 `H001` 抖动。它**不是本轮的改动**，本文件不为它背书；
> 审计本轮时请**排除 #207**。

### 1.1 四个 blob SHA（在此 SHA 上，可直接比对内容是否被替换）

| 文件 | blob SHA |
|---|---|
| `src/design_lab/native_assets.py` | `a6587e8974f960aee4a14938792647cb5dbfda95` |
| `design-lab/tests/test_bundle_deliveries.py` | `5f16659e22da36432e08fc6bddc343e81ecb9128` |
| `docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/NEXT-ROUND-PLAN-BUNDLES-LIST.md` | `7ef45a67ff2b2c9d3fbc6b5dedac71e3d6661c2a` |
| `docs/handoffs/DESIGN-LAB-BUNDLES-LIST-QUERY-ROUND-2026-09-28.md` | `ec7087f6c08d9f7f4ca15cf0906ad0acffae5454` |

### 1.2 匿名可读性（已实测）

对一个**无 token** 的读者，以下 URL 返回 **HTTP 200**（已用 HEAD 实测）：
- `https://raw.githubusercontent.com/DTALEX66/DESIGN-LAB/010f6a57610214fa41651861e00319f88a2f49a4/src/design_lab/native_assets.py`
- `https://raw.githubusercontent.com/DTALEX66/DESIGN-LAB/010f6a57610214fa41651861e00319f88a2f49a4/design-lab/tests/test_bundle_deliveries.py`

---

## 2. 可证伪的断言（逐条给 VERIFIED / FALSIFIED / UNVERIFIABLE）

| # | 断言 | 怎么证伪 |
|---|---|---|
| C1 | `native_assets.py` 的 bundle 查询谓词是 `a.asset_kind='other' AND a.asset_id LIKE 'bundle-%'`，**不是** `'design-bundle'` | 读该文件 `Bundles.list` 的 SQL（约 L88–L95） |
| C2 | 同一查询在**响应**里返回 `kind='design-bundle'`（约 L96） | 同上；注意「列值 `other`」与「响应标签 `design-bundle`」是两件事 |
| C3 | asset 表的 CHECK 约束**不含** `'design-bundle'` | 读 schema / 初始化 SQL 里的 `asset_kind IN (...)` |
| C4 | `native_bundles.py` 以 `asset_kind='other'`、`asset_id='bundle-'+<id>` 注册 bundle | 读 `native_bundles.py` 的 `register_asset` 调用（约 L73） |
| C5 | `'design-bundle'` 在 `native_bundles.py` 里只是**返回/语句标签**，不是列值 | 同文件；确认它不出现在任何 `asset_kind=` 实参位 |
| C6 | **没有任何 HTTP 路由**能到达 `Bundles` | 在 `http_service.py` 中检索 `Bundles` / `/bundles` 路由 |
| C7 | 测试文件含 5 条测试，覆盖：空项目→`[]`、未知项目→404、前缀过滤（raster 与非前缀 `other` 均缺席）、最新 ACTIVE 版本胜出、跨项目不可读 | 读测试文件的方法名与断言 |
| C8 | 必需 CI 上下文为 **9** 项，且 `CI artifact proof (H001…)` **不在**其中 | GitHub → Settings → Branches → `main` 保护规则 |

**若 C1 被证伪（即你看到 `asset_kind='design-bundle'`），那是严重缺陷**，因为该值在该表
CHECK 约束下永远匹配不到任何行 —— 查询会静默返回空列表，看起来却完全合理。

---

## 3. 明确**未做**的部分（不得算作已完成）

1. **HTTP 路由未实现。** `Bundles` 类**没有任何路由**：服务与 UI 都到不了它，
   **只有它的测试在调用它**。`GET /api/projects/<32hex>/bundles` 尚未落地。
2. **前端「最近交付」面板未实现。**
3. D-6（`/assets` 语义）只解决一半：仅证明「交付」不必靠改 `/assets` 语义取得。
4. W06 Token 写 API、W05 可纠正对象、DesignIR/RIR 映射、验收线 4、W14 剩余项、W02（被 D-3 阻塞）、W01、W07/W15 —— 均未开始。

**Evidence 等级：E2 `CONTROLLED_RUNTIME`。E3/E4/E5 未达成。**
（`host_live` 1/28、`delivery` 0/28；真实宿主验收需 Adobe 系硬件。）

---

## 4. ⚠️ 两处会被误读的红色 CI —— 请先读本节再下结论

本轮两个 PR 的 head 各触发**两次** `Canonical Verify`，**各有一次是红的**：

| PR | head SHA | 绿 run | 红 run |
|---|---|---|---|
| #205 | `e5935b551bdaa97af5189395203ccac622ae9e68` | `36499041438` ✅ | `36499046364` ❌ |
| #206 | `3b93adee4006fc7fded88b7f39d31557503122a0` | `36500594293` ✅ | `36500599140` ❌ |

**两次红 run 的失败 job 完全相同，且只有一个：**
`CI artifact proof (H001: main-run upload readback)`（各 run 共 10 job：9 成功 + 1 失败）。
**H001 不在必需检查清单内**（见 C8），属 advisory/flaky。

**而两个 main run 是 10/10 全绿（0 个非 success job）：**

| main SHA | run | 结果 |
|---|---|---|
| `b86c6da…` | `36499702629` | ✅ 10 job 全 success |
| `010f6a5…` | `36501310080` | ✅ 10 job 全 success |

**结论：不得把这两次红 run 当作「必需检查失败」。** 请核到 job 名级别再判定。

---

## 5. 本地独有产物（**网页审计无法验证**，如实披露）

`.project-local/` 被 `.gitignore:71` 忽略，故下列文件**不在云端**、网页 GPT **无法**读取。
给出哈希仅供本地持有者比对，**不构成云端证据**：

| 文件 | sha256 |
|---|---|
| `commit-bundles-list-query.txt` | `8422f90f402ae97d144d1860f6759b8cfaf2e2b3c9575744b848f89e8a19157e` |
| `commit-plan-doc-correction.txt` | `d8529288ca20269148ec3669b533b609a6ba31eabd3b274e6075cd7b1f8e021b` |
| `pr-body-bundles-list-query.md` | `edb0921d82448fbffaa57bc27905843297737bf72efb4d96265a8f40c7a073da` |
| `main-ci-010f6a5.log` | `666769f37956b86d3f815de2ae37385c12fb22fd460c45895fc1d733efb400a1` |

---

## 6. 可直接粘贴给网页 GPT 的审计提示词

```text
你是独立审计员。目标仓库：github.com/DTALEX66/DESIGN-LAB（public）。

【第一步·必须】读取并声明你实际观察到的 main 的 exact SHA。
预期审计目标 SHA = 010f6a57610214fa41651861e00319f88a2f49a4。
若不同，以你读到的为准，并明确指出差异。按 /AUTHORITY.md
(DL-AUTHORITY-2026-09-18-R2)：云端审计必须声明 exact observed SHA。

【背景】本轮把「项目交付物列表」的查询层落地，并更正了一个错误前提：
原先计划断言「交付 = asset_kind='design-bundle'」，但该值不在 asset 表 CHECK 约束内
(raster|vector|text|audio|video|blend|psd|ai|doc|other)，按它查询会永远返回空列表。
真实谓词是 asset_kind='other' AND asset_id LIKE 'bundle-%'。

【请逐条判定 VERIFIED / FALSIFIED / UNVERIFIABLE，并给出你据以判断的 URL 与行号】
C1 在 src/design_lab/native_assets.py 中，Bundles.list 的 SQL 谓词是
   a.asset_kind='other' AND a.asset_id LIKE 'bundle-%'，而不是 'design-bundle'。
C2 该查询在响应里返回 kind='design-bundle'（响应标签），与列值 'other' 是两件事。
C3 asset 表的 CHECK 约束不包含 'design-bundle'。
C4 native_bundles.py 以 asset_kind='other'、asset_id='bundle-'+<id> 注册 bundle。
C5 'design-bundle' 在 native_bundles.py 中只是返回/语句标签，不是列值。
C6 没有任何 HTTP 路由能到达 Bundles —— 在 http_service.py 中检索 Bundles 或 /bundles。
C7 design-lab/tests/test_bundle_deliveries.py 含 5 条测试，覆盖：空项目返回 []、
   未知项目 404、前缀过滤（raster 与非前缀 other 资产都缺席）、最新 ACTIVE 版本胜出、
   跨项目不可读。
C8 main 的必需 CI 上下文是 9 项，且 'CI artifact proof (H001: main-run upload readback)'
   不在其中。

【重要·防止误判】两个 PR head 各触发两次 Canonical Verify，各有一次是红的，
但两次红 run 的失败 job 都只有一个：'CI artifact proof (H001: main-run upload readback)'
（10 job = 9 成功 + 1 失败）。该检查是 advisory/flaky，不在必需清单内。
而两个 main run 是 10/10 全绿：
  b86c6da -> run 36499702629 全 success
  010f6a5 -> run 36501310080 全 success
请核到 job 名级别，不要把红 run 直接当作必需检查失败。

【请同时确认以下"未做"是否确有被夸大为已完成】
- HTTP 路由确实不存在（Bundles 只能被其测试调用，服务与 UI 到不了）。
- 前端"最近交付"面板不存在。
- Evidence 等级仅为 E2 CONTROLLED_RUNTIME；E3/E4/E5 未达成；host_live 1/28、delivery 0/28。

【可用锚点】
- 审计目标 SHA: 010f6a57610214fa41651861e00319f88a2f49a4
- blob SHA: native_assets.py a6587e8974f960aee4a14938792647cb5dbfda95
            test_bundle_deliveries.py 5f16659e22da36432e08fc6bddc343e81ecb9128
- 匿名 raw 读取应返回 200:
  https://raw.githubusercontent.com/DTALEX66/DESIGN-LAB/010f6a57610214fa41651861e00319f88a2f49a4/src/design_lab/native_assets.py
  https://raw.githubusercontent.com/DTALEX66/DESIGN-LAB/010f6a57610214fa41651861e00319f88a2f49a4/design-lab/tests/test_bundle_deliveries.py

【输出要求】
1. 先声明 exact observed SHA。
2. C1–C8 逐条结论 + 证据 URL/行号。
3. 明确列出你**无法**验证的项目（例如 .project-local 下的本地产物，被 .gitignore:71 忽略，不在云端）。
4. 给出一句话总判定：本轮是否被诚实陈述。不要复述本提示词，不要客套。
```

---

**END —— 本文件是审计入口，不是权威；权威见 `/AUTHORITY.md`。**
