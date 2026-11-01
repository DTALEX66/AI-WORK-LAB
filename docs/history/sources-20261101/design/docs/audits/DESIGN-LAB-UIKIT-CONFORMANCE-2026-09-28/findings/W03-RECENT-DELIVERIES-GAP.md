# 「最近交付」为什么暂时不能实现（判定缺口）

**性质：** 只读调查 + 结论。**本轮没有实现该面板**，因为**无法诚实地判定什么算一次交付**。
**依据：** 包内 `01_RESEARCH_AND_PRODUCT §101` 要求首页显示「继续项目、待确认、失败待修、**最近交付**」。

---

## 1. 调查（实测）

| 问题 | 结果 | 证据 |
|---|---|---|
| 服务如何表达「一次交付」？ | 导出产生一个**资产**，`kind='design-bundle'` | `src/design_lab/native_bundles.py:89` |
| 导出入口 | `export_bundle(...)`；HTTP 面是 `/api/projects/{id}/bundles/bundle-native-…/versions/…` | `native_bundles.py:29`、`native_tasks.py:133`、`http_service.py:155` |
| 资产清单里能按 `kind` 过滤吗？ | **不能。** 实测 `/assets` 返回的字段是 `id / version_id / sha256 / byte_size / rights / width / height / media_type`——**没有 `kind`** | W04 记录（`findings/W04-REFERENCES.md` §3.1）与 `image_assets.py` 的列投影 |
| 能否用别的字段代替？ | 不能**验证**。`media_type` 可能对 bundle 是 zip 类，但那是**推断**；且要产生一个真实 bundle 需要**真实 native 宿主**（本会话无此条件） |
| 任务侧能否代替？ | 任务 `kind` 只有 `native-host-published` / `primary` 之类，**不等于**交付；把任务行标成「交付」就是给真实数据贴编造标签 | `native_tasks.py:169,181` |

## 2. 结论

> **在没有 `kind` 字段（或一个 bundles 列表路由）之前，任何「最近交付」面板都必须靠猜。**
> 猜出来的判定会把**非交付**的任务/资产显示成交付——这正是本项目一直在拒绝的那类谎报。

因此本轮**不做**该面板，**只记录缺口**。这与上一轮的处理一致（上一轮也明确写为「等判定明确后补」）。

## 3. 解除阻塞的路径

### 3.1 ⚠️ 更正：上一版记录的第 1 条路**是错的**

上一版写「把 `kind` 投影进 `/assets` 读回即可解除阻塞」。**再次核对源码后，这是错的**：

```
-- src/design_lab/image_assets.py:48  `_read`
SELECT a.asset_id, v.version_id, f.path, f.sha256, f.byte_size FROM asset a
JOIN asset_version v ON a.asset_id=v.asset_id JOIN artifact f ON f.version_id=v.version_id
WHERE a.project_id=? AND a.asset_kind='raster' AND v.state='ACTIVE' ...
```

该查询在 **WHERE 里硬过滤 `asset_kind='raster'`**，且选列里**根本没有 `asset_kind`**。因此：

> **`/assets` 按构造只包含 raster，永远不可能包含 `design-bundle`。**
> 所以「投影 `kind`」对「最近交付」**毫无帮助**——那列即使补上，值也恒为 `raster`。

这条更正很重要：若照上一版的记录去做，会得到一个**看起来补齐了字段、实际永远筛不出交付**的实现。

### 3.2 真正可行的路径（都改服务端）

1. **新增「按项目列出交付（bundle）版本」的路由**——现有
   `/api/projects/{id}/bundles/bundle-native-…/versions/…` 是**单条资源**，不是列表。
2. 或**新增交付专用查询**，与 raster 资产清单分开。**不要**放宽 `_read` 的 raster 过滤：
   那会改变 `/assets` 的既有语义，并可能影响 W04 已交付的参考面板。

### 3.3 顺带更正 W04 §3.1 的归因

`contracts.ts` 的 `AssetRecord` 声明了 `kind`/`version_no` 而 `/assets` 不返回——按上面这条查询，
**这不是漏投影，而是路由语义（raster-only）**。要让 `/assets` 返回 `kind`，先要决定
「`/assets` 是『所有资产』还是『所有 raster』」——**这本身是一个语义决策，属待裁决项**。

## 4. 本轮未改任何产品代码

工作区与远端 `main` 保持不变（`93cb1cde54106d5ad07fa25e382a22a074c1f418`）。本轮产出**只有本文件**。
