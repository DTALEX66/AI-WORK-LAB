## 范围

DESIGN-LAB P1-3：库索引 4 文件一致性守卫（纯 stdlib cross-check，fail-closed）。用户全量指令的后端轻量批次。

P1-3 是 DESIGN-LAB 库索引红线的机器守卫：4 个库索引文件独立维护会漂移，必须 cross-check。现有 `verify_external_assets_index.py` 只查单文件 schema + root 声明，**未做 4 文件一致性 + 根盘符不变量**。

## 新增

`design-lab/scripts/verify_library_index_consistency.py` — cross-check 4 文件互指一致性 + "每个 shared root 必须在本地 `D:` 盘" 不变量（E: 保护盘，C: 非声明库盘）。纯 stdlib、只读、fail-closed。

4 文件：

| 文件 | 角色 |
|---|---|
| `.project/paths.json` | shared_inputs 4 根（单一真值源） |
| `design-lab/config/external-assets-index.json` | shared_roots + asset ids |
| `design-lab/readiness/model-radar.json` | asset_index_ids → index ids |
| `design-lab/config/task-resources.json` | external/model refs → roots |

5 类不变量：
1. `paths.json` shared_inputs 每根在 D: 盘
2. `external-assets` shared_roots 的 key 必须声明于 paths.json，值在 D:，且值与 paths.json **一致**（不一致 = 本守卫要抓的漂移）
3. 每个 asset 的 `shared_root` 必须是已声明 key
4. 每个 model-radar entry 的 `asset_index_ids` 指向存在的 index id
5. `task-resources` 的 external/model refs 指向已声明 shared_inputs key；每个 task refs 都是已声明资源

刻意**不 probe 外部根是否存在**（跨机不同，是本地库存任务，与 `verify_external_assets_index` 同立场）。`task-resources.json` 缺失合法（其自身 note 声明 preflight 可回退 paths.json），缺失时跳过 (5)。正斜杠/反斜杠路径归一化比较（`D:\a\b == D:/a/b`）。

## 测试

`design-lab/tests/test_library_index_consistency.py`（11 用例）：每类不变量 + 真实入库 4 文件自洽 + 漂移检测（非 D 根 / 路径不一致 / 悬空 asset_index_ids / 未声明资源 ref / 未知 shared_root）+ task 缺失合法。

## CI 挂载

`canonical-verify.yml` python-gate（Domain Pack 之后）：
```yaml
- name: Library index 4-file consistency guard (P1-3)
  run: python design-lab/scripts/verify_library_index_consistency.py
```
CI 的 `run_python_tests.py` 用 `unittest discover(test_*.py)` 自动发现新测试 → 守卫的 fail-closed 回归被覆盖。

## 验证（真实执行）

- 守卫脚本对真实 4 文件 **PASS**（shared_inputs=4 shared_roots=2 assets=5 radar_entries=14 task_resources=present）
- 单测 **11/11 OK**
- 纯 stdlib，本地裸 python 与 `.venv` 均跑通
- **不碰外部系统 / 不下载 / 不运行模型 / 不触发宿主**，CI 跨平台可跑

## 边界（按用户指令保留任务文档不执行）

P1-2（branch-protection admin PUT）/ P1-4（Adobe/MiniMax 真实宿主 E3）/ P1-5（H3 license+≥24GiB GPU）/ E3/E4/E5 = 实操自动化，**本轮不执行**。

## Evidence

E1（静态合同守卫）+ E2（真实 4 文件 + 漂移场景 fixture 验证）。
