# DESIGN-LAB：同日早一轮证据保留说明

本包主体来自最近一轮审计；为避免拆分漏掉先前已交付的本项目线索，本文件保留三个补充检查和一个原始 CI artifact。它们不依赖旧双项目总包，原始附件已经带入本包。历史记录不等于当前重新验证。

## 1. D6：资产分支 tip

此前在 `src/design_lab/creative/asset_versions.py` 发现 `branches()` 的 `MAX(version_id)` 与 `branch_tip()` 按 `version_no` 排序不一致；底层 ID 使用 UUID。`14_BRANCH_TIP_COUNTEREXAMPLE.json` 保留隔离 SQL 反例。它不是在当前工作树运行的产品回归；按实际 SHA 重读、补测试、最小修复。没有证据证明用户真实作品已受损。[D-VERSION,D-STORE]

## 2. D7：宿主环境声明

此前控制矩阵旧“Adobe 未安装”说明与 AGENTS 已安装声明不一致。保留为待核对来源/机器/时间的冲突，使用配置指定的已授权路径探测；不因云端 runner 或默认 C 盘未匹配而重装。[D-MATRIX,D-AGENTS,D-PATHS]

## 3. D8：恢复测试范围

此前读取的幂等恢复测试通过真实 HTTP 重复请求并检查 SQLite，但“首次成功返回后重试”本身不证明真实断线/崩溃恢复。保留已有用例，追加受控故障注入与读回，不把注释当已发生的测试。[D-REPLAY]

## 4. 实际保存的受控浏览器 artifact

原始压缩包：`16_ORIGINAL_CI_E2_ARTIFACT.zip`；内层摘要副本：`15_CI_E2_ARTIFACT_READBACK.json`。run=`35546749035`，subject SHA=`6a16c40b7a48f72757a0327ec07462d23449bb11`。

本次只复算已保存 ZIP 哈希、验证 ZIP CRC 并比对内层 JSON；结果与早一轮记录及副本一致：

```text
sha256:aab867d7a21b029a9819c5dc49bc43d612fa19fb3a2d71e4f267f984f408338a
```

内层 `PASS` 是该历史 Workbench E2 流程的结果，不是本次执行结果，不代表 PR #135 新路由覆盖、真实 Photoshop/Illustrator E3、人工 E4 或所有 artifacts 都已校验。最近一轮报告“未完整进行 artifact 校验”的边界仍保留；这里补充的是一个已保存 artifact 的字节证据。
