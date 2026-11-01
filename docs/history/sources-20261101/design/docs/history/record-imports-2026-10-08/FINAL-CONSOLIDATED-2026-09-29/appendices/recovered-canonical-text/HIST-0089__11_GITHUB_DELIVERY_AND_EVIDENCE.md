# GitHub 交付与证据闭环

## 默认状态

完成本地实现和复审后停止在 `READY_FOR_USER_APPROVAL`。默认不 commit、不 push、不创建 PR。

## 用户授权发布后

1. 确认 frozen tree 未变化；
2. commit 必须指向 reviewed tree；
3. push feature branch，不直接推 main；
4. 可选创建 draft PR；
5. 等待 required workflows 对 exact head SHA 完成；
6. 校验 workflow 名、run attempt、headSha、status 和 conclusion；
7. 保存 PR、run、检查和 rollback 证据；
8. 未获得管理员权限时只生成 Ruleset 模板，不声称已应用。

## 建议 Required Checks

- `governance-linux`
- `governance-windows`
- `manifest-schema-contract`
- `source-license-security`
- `visual-quality-smoke`
- `dependency-review`
- `codeql`
- `release-package-contract`

## 发布证据

- baseline HEAD/tree；
- frozen/approved tree；
- commit SHA/tree；
- remote branch SHA；
- PR URL；
- workflow run ID/URL/attempt；
- required check conclusions；
- artifact manifest/hash；
- clean worktree；
- rollback 命令。
