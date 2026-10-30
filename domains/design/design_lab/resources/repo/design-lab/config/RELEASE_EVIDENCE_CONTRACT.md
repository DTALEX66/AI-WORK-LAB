# Branch / PR / exact-SHA Evidence Contract（ODA4-0107）

## 规则
1. **旧绿色 CI 不可复用**：一次在 SHA-X 上通过的 CI，不是当前树 SHA-Y 的证据。
2. **每个 release claim 绑定**：`branch` + `head_sha` + `tree_sha` + `worktree` + `workflow name/run id/attempt`。
3. **无远端权限时明确 BLOCKED**，不得虚报验证通过。
4. 机器可读：`design-lab/schemas/release-evidence.schema.json`。
5. 校验脚本：`design-lab/scripts/verify_release_evidence.py`。

## release-evidence.json 模板
```json
{
  "schemaVersion": "design-lab/release-evidence/v1",
  "capability_id": "commercial-design-core",
  "subject": "uiux-golden-scenario",
  "version": "1.0",
  "branch": "<branch>",
  "head_sha": "<40-hex>",
  "tree_sha": "<40-hex>",
  "worktree": "clean",
  "evidence_level": "E4",
  "state": "PASS",
  "claim": "release verified",
  "environment": "github-actions",
  "ci": {
    "workflow_name": "Canonical Verify (V4)",
    "run_id": "<run-id>",
    "attempt": 1,
    "head_sha": "<40-hex must equal top-level head_sha>",
    "conclusion": "success",
    "url": "https://github.com/DTALEX66/DESIGN-LAB/actions/runs/<run-id>"
  },
  "reviewer": "codex-reviewer",
  "timestamp": "<ISO-8601>",
  "read_back": {
    "remote_sha": "<40-hex>",
    "remote_branch": "main",
    "verified": true
  }
}
```

## 校验
```bash
python design-lab/scripts/verify_release_evidence.py <evidence.json>
# 输出 RELEASE_EVIDENCE=OK 或 =FAIL（head/tree/CI/readback 任一不匹配即 FAIL）
```

## CI/PR 证据检查清单
- [ ] CI run 的 `head_sha` == 证据的 `head_sha`（防止复用旧 SHA 的绿 CI）
- [ ] `origin/main` 远端 SHA 读回 == 声明的 `remote_sha`
- [ ] 本地 branch/HEAD/tree == 证据记录
- [ ] worktree clean
- [ ] 无远端读回权限 → 状态 `BLOCKED`，不冒充 PASS

## 边界
- 未授权时不 push / 不开 PR / 不 merge main / 不 tag / 不 release。
- 所有发布 claim 必须绑定到当前 exact tree 的真实 CI attempt。
