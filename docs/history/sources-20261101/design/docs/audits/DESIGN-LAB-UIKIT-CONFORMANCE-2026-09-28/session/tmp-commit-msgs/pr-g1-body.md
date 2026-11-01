# G-1 / B1：全 git 历史 secret 扫描器 + CI gate

对应 `docs/audits/DESIGN-LAB-CLOUD-AUDIT-2026-09-23-CROSSWALK.md` 的 **B1（R12）**。

## 为什么
现有 G040（`verify_supply_chain.py`）只扫**当前 tracked 文件**；一条被 commit、分支、
force-push 过的凭据仍活在 git 对象图里。B1 补全 git 历史维度。

## 改动
- `scripts/verify_secret_history.py`（新）：`git rev-list --objects --all` 枚举全部 blob
  修订；`cat-file --batch-check` + `cat-file --batch` 批量取数（bulk write + 读全量，
  消除 Windows 逐对象管道往返，全历史 11k blobs 约 3s）。**复用** verify_supply_chain 的
  同一套 `SECRET_PATTERNS` / `is_synthetic` / `load_adjudications`——单一规则源，历史扫描
  与 HEAD 扫描永不漂移。redaction 契约：报告只存 value 的 sha256 + 3/3 端，不落全值。
  fail-closed：git 失败 / 读不到的对象 / 触 cap 都是 FAIL，绝不静默 PASS。
- 取数解析带 id 回显校验 + 边界杂字节自适应：标准布局与本机构建（每条 body 后多一个
  `\n`）都正确，任何更深错位 fail-closed。
- `verify_supply_chain.py`：`SYNTHETIC_MARKERS` 加 `your_`（对称 `your-`），豁免 inert
  research 文档里的 `YOUR_*` 占位符（如 `YOUR_RAPIDAPI_KEY`）。值内容规则、非路径规则；
  真凭据仍被 credential-shape 子句拦住。
- `design-lab/tests/test_secret_history_scan.py`（新）：12 个 hermetic 用例。
- CI `license-secret-gate`：`fetch-depth: 0` + 全历史扫描 step（`--max-blobs 0`）+ 报告
  作 artifact（`if: always()`，FAIL 也留证据）。
- `.gitignore`：`SECRET-HISTORY-REPORT.json` 不入 Git（退出码即门，避免与 drift gate
  形成 rebind 循环）。

## 验证（本机真实执行）
- 12/12 单测通过（`python -m unittest design-lab.tests.test_secret_history_scan`）。
- 全历史扫描：**6760 blobs / 0 hits / 0 failures / ~3s，PASS**。
- G040 head 门回归：`SUPPLY_CHAIN=PASS checks=9 failures=[]`（marker 改动未破坏 HEAD 扫描）。
- 零回归：与 main 基线同条件跑 `scripts/run_python_tests.py`，failures 两边均为 28
  （全为 `No module named 'PIL'/'numpy'`，本机系统 Python 无依赖；CI 用 `uv sync --locked`
  的 Py3.12 venv）。failing-classes diff 唯一新增是 `test_workbench_design_layer_e2e`
  skip→error，根因同为 PIL 缺失，与 G-1 无关。
- 两个脚本纯 stdlib（CI license-secret-gate 默认 python 无 uv 也能跑）。

## 不做（owner-gated / 其他 task）
- 历史里**未发现真凭据**（12 个 pre-marker 命中全为 inert 文档占位符），无需 redact 历史
  / force-push。若未来某次 CI 报真 hit：按报告 `introduced_in` 走处置流程（owner 决策）。
