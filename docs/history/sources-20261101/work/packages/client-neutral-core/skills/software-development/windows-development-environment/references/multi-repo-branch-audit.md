# 多仓库分支计数审计 + 上游 fork 分支识别（validated 2026-08-14）

用户报 "main 又有 N 个（分支）" 时，先定位 N 属于哪个仓库，再决定清理——不要假设。

## 审计方法

```python
# 1. 枚举用户全部仓库
GET /users/{owner}/repos?per_page=100
# 2. 每个仓库分支计数
GET /repos/{owner}/{repo}/branches?per_page=100   # len() = 分支数
# 3. 对候选仓库用 closed PR 的 head.ref 标注"已合并可删"
GET /repos/{owner}/{repo}/pulls?state=closed&per_page=100
```

实测 2026-08-14（DTALEX66）：DESIGN-LAB=12、WORK-LAB=44、hermes-agent=100、
其余 9 仓 1–3 个，合计 184。"141" 不在任何单仓——用户报的数可能是页面视图
组合或过期印象，**以 API 实测为准**。

## 上游 fork 分支识别（关键，防误删）

**hermes-agent 100 个分支里只有 1 个来自已合并 PR 的 head**——其余 99 个是
**上游 upstream 仓库的贡献者分支**（`bb/*`、`austin/*`、`alice/*`、`add-*`、
`atropos-*` 等命名），fork 同步时从上游拉下来的。**这些分支绝对不能删**——
它们是上游同步来源，删除会破坏 fork 与上游的对应关系。

判断规则：
- 分支名符合 `bb/`、`austin/`、`alice/` 等个人前缀 → 上游贡献者分支
- 分支在 closed PR 的 head.ref 里（本 fork 的 PR）→ 才是可清理的
- `merged_at` 非空 + head.ref 匹配 → 已合并可删（squash-merge 下 git 祖先链不可靠，用 API）

## 结论模式

对 DESIGN-LAB 这类**自建仓库**：12 分支中 9 个是 PR #72–#76 合并后未删的 head
分支 → 批量 DELETE。对 **hermes-agent 这种上游 fork**：99/100 分支是上游的，
**不动**（只删本 fork 已合并 PR 的 head，且确认它不属于上游命名模式）。
