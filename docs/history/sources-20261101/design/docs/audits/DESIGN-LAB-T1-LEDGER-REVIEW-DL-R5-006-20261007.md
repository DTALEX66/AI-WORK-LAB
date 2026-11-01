# T1 账本逐任务复核 · 第六项：DL-R5-006

- 观测 SHA：`efe8a67b7944af04263ee6f260f72b616b8122f8`（本次读回的 `refs/remotes/origin/main`）
- 复核日期：2026-10-07
- 账本：`design-lab/config/task-ledger-r3.json`（**只读**，未改任何状态字段）
- 顶层权威：`/AUTHORITY.md` → `.project/governance/authority-index.json` → `AGENTS.md` → 本账本

## 一、任务实况

| 字段 | 值 |
|---|---|
| title | 软件与模型资格选择 |
| priority / depends_on | P0 / `DL-R5-001` |
| required_axes | implementation / unit / **host_live** |
| implementation / unit | `PARTIAL`，共用 `r5-006-static-unit-20260928` |
| host_live / delivery | `PARTIAL`，证据数组**为空** |

acceptance：A1 拒绝不合格 candidate；A2 未知给出具体阻塞；A3 不从时区推定地域；
A4 不把个人非商业自动当全部第三方许可。
实现要求还多一句：**软件 MiniMax Design、H3 本地模型、云 API 三者分开**。

**结论：A3 成立；A1 在模块内成立但没有生产调用点；A2 大体成立、有 4 处具体坍缩；
A4 无实现；三者分开只做到了 1/3。四条轴一律不抬。**
本记录的主要用途是 §四：**"fail-closed runtime resolver" 在产品里没有任何调用路径，
而唯一直接跑真实配置的测试是空转通过的。**

## 二、逐条核验

资格判定分散在**三个互不相连**的模块，没有共享闸门：

- `src/design_lab/runtime/profile_resolver.py:128`（`resolve`）—— 实现要求所指"当前实现"
- `src/design_lab/readiness/model_radar.py:161`（`resolve`）
- `src/design_lab/creative/media/audio_provider.py:257,483`

### A1「拒绝不合格 candidate」— 模块内成立，逐因有缺口

`profile_resolver.resolve` 的检查顺序（可在代码里逐行对齐）：
`default_enabled`(`:170`) → 证据存在(`:173`) → schema 合法(`:175`) → 新鲜度(`:178`) →
`repo_sha/os/host_version/adapter_version/profile_id` 绑定(`:180-187`) → E2+(`:188`) →
launch/readback/rollback(`:190-192`) → 条件项(`:193-199`) → purpose(`:200`) →
region(`:202`) → 资源容量(`:204-207`) → 能力(`:208-214`) → fixture/artifact hash(`:215-217`) →
模型 checksum(`:218-221`)。这套顺序本身是**真 fail-closed**。

按 AGENTS.md 列的四个必拒原因逐因核对：

| 原因 | profile_resolver | 别处 |
|---|---|---|
| 零 checksum | **只在 `kind == "model"` 分支内**（`:218`），host 条目根本没有 checksum 闸门 | `model_radar.py:99-101,109-112`；`audio_provider.py:505-509` |
| 许可冲突 | **无"冲突"概念**，只有 `conditions.license` 状态字符串（`:196-197`） | `model_radar.py:174-177` 有 `BLOCKED_BY_LICENSE`；`audio_provider.py:511-515` 查 `license_denied()`，但 `denied_licenses`（`:267-275`）**只能由构造函数参数传入，`design-lab/config/` 里没有任何配置提供它** → 开箱状态下该分支永远不会触发 |
| 模型不存在 | **不报阻塞**：未知 `manual_profile` 直接 `selected=None`，既无 blocker 也无 rejected 条目（`:238-243`） | `model_radar.py:169-171`、`audio_provider.py:497-498` 有 |
| 硬件不足 | **可选**：容量检查（`:204-207`）只遍历调用方传入的 `resources`，传空即整段跳过，且不读任何机器清单 | `model_radar.py:181-189` 对 EXCEEDS 与 UNKNOWN 都拒 |

### A2「未知给出具体阻塞」— 大体成立，4 处坍缩

主体是好的：`block(code, detail)`（`:168`）带原因码，`reasons` 汇总（`:224`）。
逐条读到的坍缩点：

1. `_fresh`（`:55-59`）对格式错误/时间戳不存在一律返回 `False`，于是"过期"和"数据是垃圾"
   都显示成同一个 `EVIDENCE_EXPIRED_OR_FUTURE`（`:178-179`）。
2. `_artifact_ok`（`:95-96`）吞掉全部异常 → 一个 `ARTIFACT_INVALID` 覆盖"缺失/被改/越根"三种情形
   （`:217`、`:199`）。
3. `:206-207` 把"容量未知（`capacity is None`）"与"容量不足（`required > capacity`）"
   合并成同一个 `RESOURCE_CAPACITY`。
4. **最该改的一处**：`:158` `purpose = evidence.get("rights", DEFAULT_PURPOSE)` ——
   purpose 缺失时被**静默补成** `PERSONAL_RESEARCH_NONCOMMERCIAL`（`:22`）。
   这不是"具体阻塞"，是替用户造了一个默认值；A2 的字面正是"未知要给出具体阻塞"。

### A3「不从时区推定地域」— **成立**

在 `src/` 全量检索 `tz|timezone|localtime|astimezone|locale|geo|region`：
所有 `timezone` 命中都是 UTC 时钟/时间戳，`tzname`/`astimezone`/`localtime` **零命中**。
region 是显式必填请求字段，缺失即拒：`profile_resolver.py:147-149`、`:202-203`
（`REGION_NOT_AUTHORIZED: "Current region is unknown or not covered."`），
另有 `:150-152` 的 tz-aware 时钟守卫。**没有任何地域推断路径。**

唯一保留：这条**没有任何行为测试**。没有测试注入一个非 UTC 时区去证明地域没被推导出来；
`test_profile_evidence.py:104` 只覆盖了"region 缺失被拒"。结论靠代码不存在支撑，
而不是靠测试支撑 —— 因此它可被一次改动静默破坏。

### A4「不把个人非商业自动当全部第三方许可」— **无实现**

全仓唯一的 rights 比较是 `purpose not in record["purposes"]`（`profile_resolver.py:200-201`）：
一个字符串对一个扁平自由文本数组（`design-lab/schemas/profile-evidence.schema.json:207-213`）。
而 `conditions` 被 `additionalProperties: false` 闭合成恰好四个键（`schema.json:183-205`），
**"逐第三方组件登记许可"在结构上无法表达**。
`LICENSES/`、`THIRD_PARTY_SOURCES_V2.md`、`capability-index.json:50`
（`"license": "proprietary (MiniMax API/weights terms)"`）都是**惰性文档，没有任何 resolver 连接它们**。
`model_radar.py:123-125` 只拒绝 `BLOCKED` + `commercial_use: PERMITTED` 的自相矛盾，
`commercial_use` 从不与请求的 purpose 比对。

所以 A4 不是"部分成立"，而是**没有对应机制**：既然没有第三方项的许可集合，
"个人非商业被自动当成覆盖全部第三方许可"这件事既没被防止，也没可能发生 ——
这是缺件，不是防件。

### 实现要求的"三者分开" — 做到 1/3

`design-lab/config/profiles.json` 共 7 条：`photoshop / illustrator / coreldraw / figma / penpot / comfyui / minimax-h3`，
且**每一条都是 `default_enabled: False` 且 `evidence: null`**（本次逐条读回）。

- H3 本地模型：**有**（`minimax-h3`，另在 `model-radar.json` 里四个权重是四条独立 entry）
- MiniMax Design 软件：**没有资格条目**，只出现在 `control-capability-matrix.json:54`
  和 `integrations/hosts/minimax-design/` —— 一个没有任何 resolver 读的 disconnected 模块
- 云 API：**没有资格条目**。`model-radar.json` 共 14 条 entry，`source.kind` 实测分布为
  `huggingface×7 / local×6 / vendor×1`，不存在 `cloud`/`api` 类别 —— 云 API 根本没有可被拒绝的资格对象

另有一处命名分裂值得记：AGENTS.md:107 写的是 **`defaultEnabled: false`（驼峰）**，
驼峰只在 `audio_provider.py:325,357,367,421` 出现，而那恰是**集成度最低**的模块；
真正被配置使用的是蛇形 `default_enabled`（`profiles.json:7,13,…,43`）。
按 AGENTS.md 的字面去找 `defaultEnabled` 会找到错的那个模块。

`model_radar.resolve()`（`:161-193`）**不读 `default_enabled`**：它只看 `radar_state`
（BLOCKED / ≠QUALIFIED）与 `hardware_fit`（EXCEEDS / UNKNOWN）。即"未 QUALIFIED 不可用"是对的，
但"已 QUALIFIED 却被管理员停用"的条目仍可 resolve。`default_enabled` 只在
`validate_registry`（`:102-104,118-119`）被校验。`audio_provider` 里 `defaultEnabled` 恒为 `False`
且没有任何代码读它。

## 四、主要发现：resolver 不在任何生产路径上，且唯一的真实配置测试是空转的

**1）三个资格模块都没有生产调用者。** 对 `src/` 全量检索
`profile_resolver|model_radar|resolve_audio_model|audio_provider` 的 import：

- `profile_resolver.resolve` 只被 `design-lab/tests/test_profile_evidence.py:13` 与
  `design-lab/tests/test_profile_resolver.py:12` 引用；
- `resolve_audio_model` / `model_radar.load_registry|resolve` 在 `src/` 内**零引用**；
  `audio_provider` 这个名字在 `src/` 里只出现在 `creative/media/__init__.py:6` 的一句 docstring。
- Python 源根只有一个（`src/design_lab/`）；`providers/` 目录实际是
  `packages/capabilities/reconstruction/providers`，与模型资格无关。

即：**AGENTS.md 承诺的"runtime resolver 必须 fail closed"在当前产品里没有任何执行路径。**
Workbench 服务、CLI、native 任务派发都不问这些 resolver。测试全绿与产品行为之间没有连线。

**2）唯一直接读真实配置的测试恰好因此空转。**
`test_profile_resolver.py:15-25` 对 psd/svg/cdr 断言 `selected is None`。
而 §二 已核对：`profiles.json` 里**所有** profile 都是 `default_enabled:false` + `evidence:null`。
所以这三条断言在**任何资格逻辑都没运行的情况下也会成立** —— 它们测的是"配置是空的"，
不是"闸门会拒绝"。**更强的信号是测试名与断言相互矛盾**：`test_psd_to_photoshop`
（`:20-22`）名字宣称选中 photoshop，函数体却断言 `selected is None`；
`test_cloud_offline_rejects_figma`（`:24-26`）用 `format: svg` 去测 figma 且同样断言 None。
这看起来是配置转为全部停用后，断言被就地改成迎合结果，而名字与意图留下了 ——
一个会随配置松紧自动维持通过的测试，不具备回归检测能力。`test_profile_resolver.py:27` 对 `minimax-h3` 断言 `EVIDENCE_MISSING` 同理。
这不是说闸门不存在（`test_profile_evidence.py` 里有大量真实拒绝用例，见 §五），
而是说：**没有任何测试能发现"resolver 没被接到产品上"这件事。**

**3）真正有行为价值的测试确实存在**（避免把本记录读成"套件是空的"）：
`test_profile_evidence.py:59/68/77/91/104/114/117/169/178/183/195/200` 逐条真实拒绝
（EVIDENCE_MISSING、每个 DENIED/UNKNOWN 条件各有独立码、绑定、资源容量、nan/inf/负数被拒而非归零、
被篡改的许可回执、未知字段）；`test_readiness_model_radar.py:105-131`、`:177-198`、
`test_media_audio.py:233-300`、`test_creative_generative.py:362` 也都是行为断言。
**A3 与 A4 两项没有任何行为测试**（§二 已注明）。

## 五、抬升结论与最小动作

**四条轴全部维持 `PARTIAL`。** `host_live` 需真实宿主/模型运行（本次未运行任何宿主或模型）；
`delivery` 无交付包验收；`implementation` 因 §四(1) 没有生产接入而不成立为 IMPLEMENTED；
`unit` 虽有大量真实拒绝测试，但 acceptance 逐条对齐后 A4 无机制、A3 无测试、
"三者分开"缺 2/3，故不抬。

最小动作（都不需要真实宿主，按性价比排序）：

1. **接上或明确不接**：要么把 resolver 放到真实派发路径（CLI/服务在加载模型或宿主前调用并遵守其拒绝），
   要么在 AGENTS.md 把"fail closed"的适用范围改写成"仅库层能力，未接入产品路径"。
   **当前文档与代码的差距本身就是缺陷**，不能靠新增测试掩盖。
2. **给 §四(2) 的空转测试加对抗者**：断言存在生产调用点（可复用 #245 里已落地的
   `production_call_sites()` 思路，作用域限定 `src/design_lab`），而不是断言 `selected is None`。
3. **A2 第 4 处坍缩**：purpose 缺失应返回具体阻塞码，不得静默代填默认用途。
4. **A3 补行为测试**：注入非 UTC 时区，断言 region 仍需显式提供且不从时钟推导。
5. **A4 需要设计决策**：`conditions` 的 `additionalProperties:false` 使逐组件许可无法表达；
   扩展 schema 属结构变更，且许可裁决权归 owner（`model_radar.py:177` 的注释自己就写了
   "licence adjudication is the project owner's decision"），因此本项应提给 owner，不由 agent 自定。
6. **"三者分开"补件**：为 MiniMax Design 与云 API 各建独立资格条目；
   顺带统一 `defaultEnabled` / `default_enabled` 命名并修正 AGENTS.md 的指向。
7. **补 `denied_licenses` 的配置来源**：`audio_provider` 的许可拒绝分支目前只能靠构造函数参数，
   开箱永不触发 —— 要么接到配置，要么删掉这个假闸门。

## 六、诚实边界

- 本次**未运行任何模型或宿主**、未联网、未改账本、未写 `.project-local` 之外的路径。
- 所有引用行号在 `efe8a67b` 上逐条复验，其中承重四条我独立复核而没有沿用二手结论：
  (i) `src/` 内三个 resolver 的生产引用为零；(ii) `model_radar.resolve()` 不读 `default_enabled`
  （实际读的是 `radar_state`/`hardware_fit`，`:169-189`）；(iii) `profiles.json` 7 条全部
  `default_enabled=False` 且 `evidence=None`；(iv) Python 源根唯一、`providers/` 属 reconstruction。
- 关于"没有 X"的结论一律配了检索范围与关键词（§二 A3、§四(1)），
  并按 005 记录的教训标注其性质：**A3 的"不存在时区推定"是由代码不存在支撑，不是由测试支撑** ——
  这是我在 005 上犯过的错的反向应用：那里的错误是把"检索没找到"当成"不存在"，
  这里我把自己找过的范围写出来，让下一个人能判断覆盖是否充分。
