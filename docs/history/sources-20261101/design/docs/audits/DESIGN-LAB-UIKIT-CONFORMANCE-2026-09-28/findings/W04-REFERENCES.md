# W04 —— 参考与资产（参考面板首片）

**状态：** W04 首片已交付并验证；包内 W04 仍有未做项（见 §6）
**证据：** `evidence/W04-REFERENCES.json`（浏览器 17 项 + 词表交叉核验 4 项）
**harness：** `harness/w04-references.mjs`（驱动器复用 `harness/w03-brief-editor-verify.py`）
**性质：** 修改产品代码（`apps/workbench/shell.ts`、`apps/workbench/style.css` + 重建 `build/main.js`）。

---

## 1. 交付

`/projects/:id` 新增**参考素材**面板：

- 读回 `GET /projects/{id}/assets`，逐行显示真实字段（尺寸、media_type、asset id、version_id、sha256）
- 「权利未审查」显式标注，并说明**未知权利阻止生产认证**
- **按需预览**：点「预览」才读 `GET /projects/{id}/assets/{asset_id}/content`
- 读不到清单时显示「未读回」，**不显示 0**

## 2. 验收对照（包内 W04 验收）

| 包内验收 | 本轮做法 | 结果 |
|---|---|---|
| **图片不被默认裁剪** | 预览 `object-fit:contain`（**实测 computed 值 = contain**；`cover` 会裁） | ✅ |
| **alpha 可见** | 预览加棋盘底（`repeating-conic-gradient`），透明区不再被当成黑/白实心块 | ✅ |
| **缺失引用可定位** | 读取失败时**点名该 asset id** 且**清掉旧图**（不留陈旧画面） | ✅ |
| **未知 rights 可研究但阻止生产认证** | 面板标注 + 明文说明；**执行在服务端**，面板只呈现不冒充执行 | ✅ |
| `鉴权图像路径` | 见 §3.2：两条**不同**事实分别断言 | ✅ |
| 大图按需生成预览 | 清单阶段 **content 请求 = 0**；点一次预览后 = 1 | ✅ |
| 批量导入可取消并报告部分失败 | **未做**（导入仍在旧工作台） | ⏳ |

`17/17` 通过（真实服务 + 生产 CSP + 已提交 build），词表交叉核验 `4/4`。

## 3. 本轮两个真实发现

### 3.1 契约与实现不一致：`AssetRecord` 声明了服务不发送的字段

`contracts.ts` 的 `AssetRecord` 声明了 `kind` 与 `version_no`；但 `/assets` 实际返回的是
`id / version_id / sha256 / byte_size / rights / width / height / media_type`（见
`src/design_lab/image_assets.py` 的列投影）——**没有 `kind`，也没有 `version_no`**。

我第一版照契约字段渲染，于是行里真的显示成：

```
1 × 1 · image/png · undefined
img-… · 版本 undefined · sha256 sha256:…      ← 还有重复的 sha256 前缀
```

**"undefined" 出现在 UI 里就是谎报**。已改为**只渲染实际存在的字段**（并用确实存在的
`version_id` 代替 `version_no`），并在 harness 里加了一条**永久门禁**：

> `no field renders as the literal "undefined"`

这条检查能在第一次运行时就抓住这个 bug——现在它守着。

**这是仓库层面的发现**：TS 契约比服务实际返回更宽，建议要么补齐服务投影，要么收窄契约
（属跨文件契约问题，本轮只从 UI 侧做到不再据此显示假值，**未擅自改契约或服务**）。

### 3.2 我自己的一条检查「因为错误的原因通过」

第一版断言是「裸 `<img src=/api/...>` 无法加载资产字节（因为鉴权只用 header）」，
实测**通过**——但浏览器日志显示原因是：

```
Loading the image '…' violates the following Content Security Policy directive: "img-src data:"
```

也就是说请求**根本没到服务**，鉴权从未被触及。**通过的原因与标签所称的原因不同**，这条检查
其实什么都没证明。已拆成两条互相独立的事实：

| 断言 | 结果 |
|---|---|
| 裸 `<img>` 被 CSP `img-src data:` 拦截 | ✅ |
| 同一 URL 用**无 Authorization 的 `fetch()`**（受 `connect-src 'self'` 管，同源允许）→ **401** | ✅ |

第二条才真正隔离了「鉴权只用 header」这一事实。**顺带记录一条硬约束**：由于 CSP 是
`img-src data:`，本项目的**任何图像 UI 都必须走 data URL**（`api()` 取字节 → base64），
不能直接用 `/api/...` 当图片地址。这对后续 W04/W10 的图像界面是设计前提。

## 4. 回归

| 项 | 结果 |
|---|---|
| W03 brief harness | 21/21 |
| W03 triage/recent harness | 14/14 |
| 仓库自带浏览器 E2E | `ran=2 skipped=0 failed=0` |
| `tsc --noEmit` / smoke / appshell | 通过 |
| `vite build` 可复现 | SHA256 一致 |

## 5. harness 自身的问题

- `await fetch(url).catch(...)` 写法把 `.catch` 挂在了**已解析的响应**上 → `TypeError`；
  且那次 fetch 本来就是多余的（asset id 已在行里）。已删。
- 驱动器新增通用结论行 `HARNESS=<kind> checks=N passed=M`（此前只打印写死的 `W03_BRIEF=`，
  共用驱动器时标签具有误导性）。
- 控制台错误归属扩展到 `bare-img` 阶段：那里的 CSP 拦截是**故意**制造的。

## 6. W04 未完成 / 未覆盖

- **导入 / 批量导入**（含「可取消」「报告部分失败」）仍在旧工作台，路由壳内**未做**。
- **无缩略图网格**：刻意不做，以兑现「大图按需生成预览」；清单只出文本行。
- 预览仅支持 `image/png` / `image/jpeg`（与服务既有 `preview()` 的限制一致）；其他类型走
  `UNSUPPORTED_PREVIEW` 分支并如实报错。
- 权利**执行**在服务端，面板不冒充执行者。
- 证据等级：**E2 CONTROLLED_RUNTIME**。

---

**END — W04 首片记录。**
