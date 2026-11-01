# 05 — C3 Illustrator 真实 E3

状态：**`BLOCKED_PERMISSION`（owner 本轮只授权只读探测，不启动宿主 GUI）**。
本轮**没有**产生新的 E3 证据，也**没有**把历史证据当作本轮成果。

## 本轮实际执行的只读探测（2026-10-05，本机 Windows 10.0.26100）

| 项 | 读数 |
|---|---|
| COM ProgID | `Illustrator.Application` 已注册 |
| CLSID | `{303D549B-3B36-47B4-8657-1B0374E2F553}` |
| LocalServer32 | `C:\Program Files\Adobe\Adobe Illustrator 2025\Support Files\Contents\Windows\Illustrator.exe /Automation` |
| 进程 | `Illustrator.exe` **未运行** |
| 登记版本（`docs/LOCAL_ENVIRONMENT.md`，2026-09-06 观测） | Illustrator 2025 / 29.5.1 |

结论：宿主**可寻址**（E1 结构级：COM 注册面存在），但 E3 必须真启动、真建文档、真读回，
本轮 owner 明确不授权启动，故停在 `BLOCKED_PERMISSION`。

## 仓库既有实现（复用，不重写）

- `src/design_lab/adapters/illustrator_com.py`：真实 COM
  （`New-Object -ComObject Illustrator.Application` + `DoJavaScript`），
  固定 JSX 桥 `reconstruction-assemble.jsx`，输入/产物 digest 封条，
  读回校验 `%PDF` 头。
- `packages/capabilities/reconstruction/native_patch_plan.py`：
  Illustrator patch 支持 `text`→`'text'`、`path`→`'points'`，
  并要求拓扑保持（`len(value) == len(found[0]['points'])`）。
- `native_patch_submissions.py`：要求先存在 **RECEIPTED** 的原生 attempt，
  并绑定 baseline/checkpoint/input hash + 幂等键。
- 历史 E3 记录（**不提升为当前**）：`docs/decisions/R3-REAL-POSTER-PATCHES-2026-09-08.md`
  曾在真实 AI 29.5.1 上改一个 live text 与一个 path 并复原。
  按 Authority §6，历史证据不自动提升新 SHA/新 adapter 版本的能力。

## 与本轮 C2 的衔接

`plan_to_rir` 保持 `object_id` 不变，因此 Plan→IR→Illustrator job 的节点 id
与 patch 定位使用同一套 id（见 `04_DESIGN_IR_EVIDENCE.md`）。
这缩短了 E3 距离，但**不构成** E3。

## 下一动作（需要 owner 授权启动宿主）

1. 授权后按 `docs/LOCAL_ENVIRONMENT.md` 的禁忌执行：隔离测试文档、
   不触碰用户正在编辑的文件、不通过杀进程清锁。
2. 用仓库既有资格运行器显式执行宿主（默认只准备，不启动）：
   `.venv/Scripts/python.exe -B design-lab/tests/host_fixtures/prepare_illustrator_lowered.py --execute-com`
   （COM 走 stdin 固定序列，只新建项目内文件，不改 profile/策略，不做 GUI 点击）。
3. 产出绑定 exact SHA + adapter version + Illustrator version +
   document/object id + artifact hash + readback + rollback 的 evidence record，
   以 `outcome=host_live` 写回唯一账本 `DL-R5-011`。
