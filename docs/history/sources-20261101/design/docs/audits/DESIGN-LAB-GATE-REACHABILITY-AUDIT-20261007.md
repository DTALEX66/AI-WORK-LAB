# 闸门可达性审计 · 2026-10-07

**观测 exact SHA**：起点 `main` = `a7eab642`；本轮工作树 = `93134b6f`
**观察窗口**：2026-10-06T23:20Z–23:27Z
**问题**：仓里有 98 个 `verify*/audit*/check*` 脚本，其中有多少**真的会被执行**？
`canonical-verify.yml` 是 SHA-256 钉死的，且它**逐步显式列举**闸门——没有 glob，也没有清单。
所以一个没人给它写 step 的 `verify_*.py` 就永远不跑，而且**没有任何地方会说这件事**。

## 一、测量方法（以及为什么第一次的数字是错的）

第一版按"文件名是否出现在 workflow 里"判断，得出 48/111 不可达。这个数**不可信**，
因为它漏掉了两类真实入口：`scripts/run_python_tests.py` 会执行它发现的**每一个**测试模块，
而测试模块可以 shell out 去调脚本；统一验证器 `verify_design_lab.py` 也会转调别的脚本。
于是改成不动点遍历：根集合 = workflow 文件 + 所有 `design-lab/tests/test_*.py`
（CI 必然执行它们），若某候选被活着的文件按名字提及则转活。结果：

```
candidates=98  reachable=85  unreachable=13
```

13 个孤儿里 5 个是 `deepseek_*` 一次性历史审计、1 个是捕获工具、1 个是探针，
**剩下 6 个是真闸门**：`verify_no_overclaim`、`verify_evidence_levels`、`verify_supply_chain`、
`verify_fresh_clone`、`verify_clean_tree`、`verify_r5_intake`。

## 二、把它们逐个跑了一遍

```
verify_no_overclaim     rc=0  NO_OVERCLAIM=PASS claims=8 supported=4 qualified=4 unsupported=0
verify_evidence_levels  rc=0  EVIDENCE_LEVELS=PASS claims_examined=4 historical_evidence_kept=4
verify_supply_chain     rc=0  SUPPLY_CHAIN=PASS checks=9 failures=[]
verify_fresh_clone      rc=1  FRESH_CLONE=FAIL stages=1 failures=['clone']
verify_clean_tree       rc=0  CLEAN_TREE=ATTRIBUTED dirty=3 unattributed=0   # 判的是工作树，CI 里恒真
verify_r5_intake        rc=0  R5_INTAKE_VERIFIED_NOT_ADOPTED tasks=28        # 历史任务包
```

三个 PASS 的闸门是**在跑且没人看**的：它们守的是"声明有没有依据"这类谎报面，
而不是计数面。本轮把这三个接进 CI。

## 三、`verify_fresh_clone` 是真坏了，而且坏得会误导人

```
FAIL clone  fatal: destination path '...fresh-clone' already exists and is not an empty directory.
```

根因不是 clone：脚本原先写的是 `shutil.rmtree(CLONE, ignore_errors=True)`。
嵌套 clone 里有 Windows 普通删除扛不住的长路径，`ignore_errors=True` 把失败咽了下去，
目录活下来，下一行 `git clone` 才报"目标已存在"——**报告把罪名安在 clone 阶段，
而真正的原因是残留目录**，且原始错误文本被丢弃。

修法：`clear_previous_clone()` 在 NT 上用 `\\?\` 长路径前缀删除，
删不掉就**把异常类型和消息作为该阶段的证据返回**并让 clone 阶段带着真原因 FAIL。
修复后本机实跑：

```
FRESH_CLONE=PASS stages=9 failures=[] unverifiable=['install']
  PASS clone / clone_head_matches / tracked_content_present(2976) / contracts_parse(121)
  PASS contract_graph(breaks=0) / reports_generate / reports_check / path_boundaries
  NOT_VERIFIABLE install   # CI 跑 uv sync --locked；本机未尝试安装，如实记不可验证
```

它仍**不**接进 CI：一次全仓 clone 约 236 MiB，而 CI 另有 clean-wheel 作业。
这条连同理由写进豁免表。

## 四、防复发：孤儿闸门元门

`design-lab/tests/test_gate_reachability.py` 断言"不可达集合 == 显式豁免表"，**双向**：
新孤儿会出现，豁免失效（脚本被接进 CI 或被删）也会出现，每条豁免必须带实质理由。
它在自己身上抓到了两个 bug，因此不是空转的：

1. 首跑报 `probe_large_asset_gate.py` 是**过期豁免**——它压根不在候选集里（不匹配 `verify|audit|check`），
   即"给一个不是闸门的东西发了免死金牌"；
2. 第二跑报 9 条豁免**其实可达**——因为元门自己的豁免表按名字列出了这些脚本，
   扫描把自己也算成了调用方。修法是把本模块从扫描源里排除。

## 五、副产发现（未处置）

- 这五个闸门各自**写 tracked 投影**（`NO-OVERCLAIM-AUDIT.json`、`EVIDENCE-LEVEL-AUDIT.json`、
  `SUPPLY-CHAIN-REPORT.json`、`FRESH-CLONE-VERIFICATION.json`、`CLEAN-TREE-REPORT.json`），
  但 `current-report-index.json` **不 digest 它们**（grep 命中 0）。
  也就是说这些"当前状态"文件与当前代码之间没有任何一致性约束——它们此前一直是陈的。
  本轮把三个实质性的刷新并提交，`CLEAN-TREE-REPORT.json` 刻意回退（它记的是某次工作树的瞬时脏状态，
  不是仓库级事实）。
- `verify_supply_chain` 报 `G000_sources_lock entries=46 urls=39 revisions=0`：
  #242 把逐源 revision 写进了 `vendor/sources.revisions.json`，而这条检查只读 lock。
  **本轮已接上**（同一提交内）：`revision_coverage` 现在同时看派生记录，实跑
  `revisions=37`，并新增 `revision_record` / `absorb_without_revision` /
  `revision_record_ids_not_in_lock` 三个字段；`test_claim_honesty_gates.py` 直接断言
  `revision_coverage > 0`，因为**少报自己覆盖率的闸门比没有闸门更坏**——那个数字正是别人信的东西。
- 接上之后立刻多出一条此前看不见的发现：`absorb_unresolved` 有**两个**而不是一个——
  `ai-product-os-frontend` 与 `front-end-design-checklist`。后者正是"已吸收"清单里那份
  CC0 的 `packages/capabilities/standards/front-end-design-checklist/`，
  即它是 `ABSORB_MINIMAL` 却没有 revision，属 AUTHORITY §9 未闭合项。
  本轮把这两个 id 钉成断言（第三个混进来就会红），处置仍需 owner/上游查证。

## 六、那 9 条无 revision 的来源能不能离线补齐——不能，而且有个陷阱

接上 revision 记录之后，自然的下一步就是"把 9 条 unresolved 也补掉"。逐个查了本地证据，
结论是**一条都补不了**，并且过程中撞到一个值得单独记的陷阱。

### 查了什么

| 来源 | 本地是否有 commit | 实际记录的东西 |
|---|---|---|
| `ai-product-os-frontend` | 无 | `SOURCE.md`：repo URL、license MIT、`branch: main`、vendored 2026-08-14、外置隔离位置与"SHA-256 回读一致" |
| `front-end-design-checklist` | 无 | `SOURCE.md`：repo URL、CC0-1.0、吸收日期 2026-08-13、吸收方式、可再分发=是 |
| 其余 7 条（`anydesign`、`claude-design-skill`、`design-system-prompt`、`motion-engine`、`shipit-ui`、`web-content-designer`、`tool-control`） | 无 | lock 的 `notes` 里**连 URL 都没有**；`tool-control` 写的是 `origin: multiple (...)` 多来源 |

`ai-product-os-frontend/skills-lock.json` 里确实有一堆哈希，但那是**每个 SKILL.md 的
`computedHash`（SHA-256 内容哈希）**，不是 git commit。

### 陷阱：40 位十六进制不等于 commit

在上述两个目录里 `grep -Eoh "[0-9a-f]{40}"` 能命中若干串——它们全是
**SHA-256 被截断到 40 位的前缀**。而 #242 那条防漂移断言用的是
`^[0-9a-f]{7,40}$`，**照单全收**。也就是说：将来任何人"顺手"用内容哈希去补 revision，
格式检查会绿，而记录会说谎——把"这份文件的哈希"当成"我们取的是这个提交"。
git 短 SHA 与 SHA-256 前缀在语法上无法区分，所以这道关不能只靠正则。

现在真正兜住的是**构造性来源**：`derive_vendor_revisions.py` 只从
`CANDIDATE-TAXONOMY.pinnedCommitSHA` 取值，且 `test_vendor_revisions` 每次重派生比对。
只要有人手工填一个哈希进去，重派生就会不一致而报错——**这条比正则重要**，
读代码的人应当知道防的是哪个。

### 因此本轮的处置

不新增离线补齐的假动作，改为把"缺什么"变成机器可见的分类：

```
revision_unresolved_with_url    = [ai-product-os-frontend, front-end-design-checklist]   # 2
revision_unresolved_without_url = [anydesign, claude-design-skill, design-system-prompt,
                                   motion-engine, shipit-ui, tool-control, web-content-designer]  # 7
resolved(37) + 2 + 7 == entries(46)      # 由 test_claim_honesty_gates 断言
```

两类的前置动作不同，且都需要人：2 条要先确定"当初取的是哪个提交"（HEAD-now 不算，
上游自 2026-08 以来可变），7 条要先确定上游是谁。`tool-control` 另有一层：
它本来就是多来源拼装，单一 revision 字段对它可能压根不适用，需要 owner 定口径。
