# 06 — C4 Photoshop 真分层 PSD E3

状态：**`BLOCKED_PERMISSION`（owner 本轮只授权只读探测，不启动宿主 GUI）**。
本轮**没有**新的 E3 证据。

## 本轮只读探测（2026-10-05）

| 项 | 读数 |
|---|---|
| COM ProgID | `Photoshop.Application` 已注册 |
| CLSID | `{18455259-BEE7-442C-89FE-DE31ED630B2B}` |
| LocalServer32 | `C:\Program Files\Adobe\Adobe Photoshop 2025\Photoshop.exe /Automation` |
| 进程 | `Photoshop.exe` **未运行** |
| 登记版本（2026-09-06 观测） | Photoshop 2025 / 26.7.0.15，COM 实测 26.7.0 |

## 仓库既有实现（复用，不重写）

- `src/design_lab/adapters/photoshop_com.py` +
  `packages/capabilities/reconstruction/adobe_job.build_photoshop_job`：
  可编辑文本层 + 独立像素层 + group / group-mask；
  读回校验 `8BPS` 头与 PNG 头；**通用矢量路径只走 Illustrator，绝不静默栅格化**。
- 资格运行器：`design-lab/tests/host_fixtures/prepare_photoshop_native.py`
  （默认只准备；显式 `--execute-com` 才调用固定 COM 序列，UUID 新目录、只新建项目内文件）。
- 历史 E2 记录（**不提升为当前**）：
  `docs/decisions/R3-PHOTOSHOP-NATIVE-ROUNDTRIP-2026-09-08.md`
  —— 受控合成案例通过两次修改/重开/恢复；
  工作台、复杂参考、UXP 实机路径仍未完成（`UXP` 侧只有 Node double，不算宿主资格）。

## 与任务书验收线的差距

任务书要求证明「文本层可编辑 / mask 可编辑 / 独立图层存在 / group 层级存在 /
重开结构一致 / 局部修改只改目标对象」，且“整张图塞进一个 layer = FAIL”。

本轮对这些**一条都没有新证据**。合同层面（E1）能确认的是：
`lower_layers` 对 raster 节点要求 `alpha==1` 且 `sourceMappings` 为空、
crop 必须已实体化，否则拒绝建 job —— 即“把整图塞一层”的偷懒路径被代码挡住，
但这只是结构约束，不是宿主证明。

## 下一动作

1. owner 授权后：
   `.venv/Scripts/python.exe -B design-lab/tests/host_fixtures/prepare_photoshop_native.py --execute-com`
2. 补齐 C2 未覆盖的 raster 前置：把参考子区域**先实体化为独立资产**
   （当前 `plan_to_rir` 产出的 raster 节点带 crop/sourceMappings，
   lowering 会要求先 materialize —— 这是刻意的 fail closed，不是 bug）。
3. 产出绑定 exact SHA + PS version + adapter version + layer 结构读回 +
   artifact hash + rollback 的 evidence，写回唯一账本 `DL-R5-012`。
