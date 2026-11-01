## 范围

审计 P1 两项治理/打包修复（Batch B/F，独立分支 `fix/backend-batch-1`，基于 origin/main）：

### P1-7 · release-gate tag 触发器（`.github/workflows/release-gate.yml`）
- `on:` 原本只有 `workflow_dispatch`，tag-only preflight 步（`if: startsWith(github.ref, 'refs/tags/')`）**不可达**——打 tag 永不触发 E5 release gate
- 新增 `push: tags: ['*']`（additive，保留 dispatch）；`*` 刻意放宽：本仓 0 tag 无命名约定，广匹配 + fail-closed gate（INCOMPLETE/BLOCKED，绝不误 PASS）不可能产生假发布；tag 约定建立后收紧为 `v*`
- 验证：YAML 解析通过，`on` = {workflow_dispatch, push}，push.tags=['*']

### P1-1 · wheel/sdist node_modules 排除（`pyproject.toml` + 守卫脚本）
- 旧整目录映射（wheel force-include + sdist only-include 的 `apps/workbench`）在开发机构建时把 `node_modules`（~30MB/251 文件）拖进 wheel，与 CI 干净 checkout 的 ~0.5MB wheel 漂移
- 现两个 target 各只含服务端实际服务的 3 个文件（workbench.py ROUTES：`index.html`/`style.css`/`build/main.js`）
- 守卫 `verify_workbench_packaging.py` check 5 扩展：要求 3 条精确 wheel 映射 + 3 条 sdist 条目，**整目录映射回归即 FAIL-CLOSED**（同类修到根，非单点）
- 验证：守卫 5/5 PASS；tomllib 断言 wheel=3 条 workbench 映射、sdist 恰为 3 文件、无整目录映射

## 风险与回滚

- 纯 CI 配置 + 打包映射 + 守卫脚本，无运行时代码改动；revert 单 commit 即回退
- wheel 内容变化仅少 30MB 无关文件，已服务文件的打包路径不变

## 候选 SHA

`cb5d26f`
