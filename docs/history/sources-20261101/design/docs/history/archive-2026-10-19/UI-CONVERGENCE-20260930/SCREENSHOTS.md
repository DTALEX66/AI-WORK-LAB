# DESIGN-LAB UI 商业级 Workbench — 截图验收（Playwright 真实浏览器）
任务包：DESIGN-LAB_UI_FRONTEND_TASKPACK_20260930 · 分支 feat/ui-commercial-workbench-20260930

> 本文件此前（commit `0fbb674`）声明「12 张截图已生成 / 真实渲染 / hash 已记录」，
> 但仓库内不存在任何 PNG，表格数值全是占位符。该声明为**假完成**，与
> `VISUAL_QA.md`（DEFERRED）、`COMPLETION_REPORT.md`（待办）互相矛盾。
> 2026-10-05 已按方案 A 修复：真实执行截图并把结果写回本文件。
> 修订记录见 `MERGE_READY_HANDOFF.md` 的 Evidence Truth Repair 段。
>
> 2026-10-06：界面多维审计修复批次（见 `UI-AUDIT-20261006.md`）改变了视觉结果，
> 本组 40 张截图已在新 commit 上**整轮重拍**并重建本文件的表格与环境块；
> 表格与 `screenshot-manifest.json` 由脚本从清单生成，不手抄哈希。

## 复现命令

```
.venv/Scripts/python.exe scripts/capture_workbench_screenshots.py \
    --widths 390,768,1280,1920,2560
```

启动器（`scripts/capture_workbench_screenshots.py`）会：
1. 探测 node / 仓内 Playwright / 本机 Chromium，缺一即 `CAP_BLOCKED` 退出，不伪造；
2. 先断言 `apps/workbench/build` 与 HEAD 无 drift（Build Output Truth），
   否则拒绝截图——截图必须是某个 exact commit 的证据，不能是未提交的本地重建；
3. 用真实 `ProjectService` + `make_server` 在 OS 分配端口上起回环服务，
   临时项目根 + 内存 64-hex token（与既有浏览器 E2E 同一合同）；
4. 交驱动 `design-lab/tests/e2e/capture_workbench_screenshots.mjs` 在真实
   Chromium 内**通过 UI 写入**数据，再逐页截图并计算 SHA-256。

## 方法（实际执行值）

- 页面：`http://127.0.0.1:<port>/workbench`（真实服务，CSP `script-src 'self';
  style-src 'self'`，classic-script `build/main.js`，零外部依赖）。
- 数据：驱动在 UI 内新建项目 → 导入真实参考图
  （`design-lab/evals/reconstruction/cases/poster-sunrise-001/reference.png`，
  192×128 PNG，非 1×1 占位）→ 持久化简报 → 立方向 → 选定方向 → 绑定设计系统。
  所有面板内容均为服务读回，**无 mock、无预填 DOM、无占位图**。
- 视口：390×844 / 768×1024 / 1280×800 / 1920×1080 / 2560×1440，共 5 档。
- 页面：`#/dashboard`、`#/projects`、`#/projects/:id`、`#/tools`、
  `#/deliverables`、`#/evidence`、`#/preflight`、`#/settings`，共 8 页。
- 每页截图前等待 KPI count-up 稳定（`strong[data-count]` 文本 == 目标值）后才拍，
  避免把动画中间帧的错误数字写进证据。
- 驱动对 `pageerror` / `console.error` fail-closed：任一出现即整轮判失败。
  本轮 40 张全部零诊断错误。

## 环境（读自 `screenshot/screenshot-manifest.json`）

```json
{
  "generatedAt": "2026-10-06T08:36:59.857Z",
  "commit": "8167e623b7c31d63567ca189b4c33215059b1acb",
  "subject": {
    "bundle": "apps\\workbench\\build\\main.js",
    "bundleBytes": 164033,
    "bundleSha256": "79ab1cf5c6228678c308f3356038ccf4210d698d6763008e498d88a30efa90b6"
  },
  "project": {
    "name": "Closeout 1791275795091",
    "id": "13ec60724577474498718544c22b508b"
  },
  "referenceSourceImage": "D:\\All projects\\DESIGN-LAB\\design-lab\\evals\\reconstruction\\cases\\poster-sunrise-001\\reference.png",
  "service": {
    "origin": "http://127.0.0.1:63107",
    "pythonVersion": "3.12.13"
  },
  "browser": {
    "engine": "chromium",
    "version": "149.0.7827.55",
    "executable": "C:\\Users\\ALEX\\AppData\\Local\\ms-playwright\\chromium-1228\\chrome-win64\\chrome.exe",
    "headless": true
  },
  "nodeVersion": "v24.18.0",
  "capture": {
    "fullPage": false,
    "mockUsed": false,
    "viewports": [
      390,
      768,
      1280,
      1920,
      2560
    ],
    "pages": [
      "dashboard",
      "projects",
      "project-detail",
      "creative-tools",
      "deliverables",
      "evidence",
      "preflight",
      "settings"
    ]
  }
}
```

## 截图结果（40 张，全部存在于 `screenshot/`）

| 文件 | 视口 | 路由 | 字节 | SHA-256 |
|---|---|---|---|---|
| `00-dashboard@390.png` | 390×844 | `#/dashboard` | 76,186 | `a5d400b52258216c630cddb5fce2d04dc99183d3bf3d5b94b7073fbf172cd395` |
| `01-projects@390.png` | 390×844 | `#/projects` | 65,556 | `e6de64669ec366570ea8a6d73d2917f4caa6632dad18d1b8de21c27f944d072d` |
| `02-project-detail@390.png` | 390×844 | `#/projects/13ec60724577474498718544c22b508b` | 63,051 | `4651fddca099c183049fe695377e73a1eadae87f0083380a05cfc987edbb0579` |
| `03-creative-tools@390.png` | 390×844 | `#/tools` | 39,179 | `3779a93e02d74450dbb5500449470657feb78eb6428fc8884cae079331a83a8c` |
| `04-deliverables@390.png` | 390×844 | `#/deliverables` | 39,825 | `a4e72f8596bdf1ca3d844e18b063541f678fe2086849c410ee4872c87b592cda` |
| `05-evidence@390.png` | 390×844 | `#/evidence` | 40,998 | `4c989d14f750ea60ceb42660e79306ac1494a28c74d2f6a6928e1d5c44dcaf88` |
| `06-preflight@390.png` | 390×844 | `#/preflight` | 67,199 | `0f3fffbcac1803ba06ecfb66a8bc7c5843216e3795a129336d78827f9aea2f2d` |
| `07-settings@390.png` | 390×844 | `#/settings` | 80,416 | `7babd93ca16311bcc2059ae683fe56a18aa7d9f37de65042154a5a0b7c9e7eb7` |
| `08-dashboard@768.png` | 768×1024 | `#/dashboard` | 103,072 | `f1ceb5e9fcd5259b561728b7f63662bfab47f0ae64b004359795d9bcb7afc68f` |
| `09-projects@768.png` | 768×1024 | `#/projects` | 88,604 | `7bd747f9e91735d5e9c7d12237cb0c18df4f16e86a0ee6d0aae1fec4fe1ee4fa` |
| `10-project-detail@768.png` | 768×1024 | `#/projects/13ec60724577474498718544c22b508b` | 88,615 | `ec4f8e86444348d18cc1235b1989e0b74e87f828afe5dd75e70f289b6e5651c1` |
| `11-creative-tools@768.png` | 768×1024 | `#/tools` | 48,903 | `30eaeb5ce5c27889a6d528fded1c924c2d2b581e8e0281cde7f443c6103c0f35` |
| `12-deliverables@768.png` | 768×1024 | `#/deliverables` | 49,548 | `0eca1a0ffcb227d23e1f42efd67803d4f17660537a0e8f673fb21202f9797e42` |
| `13-evidence@768.png` | 768×1024 | `#/evidence` | 50,612 | `04621cc73e83276506784b6f3ebd32b9c01734c0167e135bdf1a2db1bf503b85` |
| `14-preflight@768.png` | 768×1024 | `#/preflight` | 84,307 | `26dc2a6a58dfc6f1008285450be874e45e064b48a740d9afd41766259bf457e6` |
| `15-settings@768.png` | 768×1024 | `#/settings` | 138,934 | `95c41727a2ab6c75106f709e901ea75eecdf9c4326a2abffcb661385e37470fc` |
| `16-dashboard@1280.png` | 1280×800 | `#/dashboard` | 184,368 | `57b0b6df156bd3cc07d6bdcd6e737c1fa0c048b7a888a68b31ad3b7db87b6af8` |
| `17-projects@1280.png` | 1280×800 | `#/projects` | 130,332 | `2a20819b10cf9a160071df1a35d3212d110f30557a4f35c8efede1ff75b656dc` |
| `18-project-detail@1280.png` | 1280×800 | `#/projects/13ec60724577474498718544c22b508b` | 166,604 | `bd158b26effa56878a8bd9c8331bb14491f4562bf379bfbcc935cc2c3ab09bff` |
| `19-creative-tools@1280.png` | 1280×800 | `#/tools` | 91,082 | `7dc2356d3e0c3a75fef57aa839bba91918240a0b782c7c14d16f2f69f8fe1606` |
| `20-deliverables@1280.png` | 1280×800 | `#/deliverables` | 91,943 | `d7a81e3449adafa7266f4a8f2fd377a2e5dc037b78feedda59e677134c4f6c1d` |
| `21-evidence@1280.png` | 1280×800 | `#/evidence` | 93,188 | `de33dc092451ce82093c2283710d5cccb5a6d47e5fe6b2127cf48dab1490c3e3` |
| `22-preflight@1280.png` | 1280×800 | `#/preflight` | 123,963 | `03abfcc319d2d51cd10c9598e9ab91afc29b78f9626e6f668877199c1cbd76be` |
| `23-settings@1280.png` | 1280×800 | `#/settings` | 198,192 | `344fb2dc5af7cb2fbb55bb67bfa3d6de86989ebdb1a505777d831f42a866c81e` |
| `24-dashboard@1920.png` | 1920×1080 | `#/dashboard` | 239,596 | `36abc911561b041b7328b94b3c1af9ae686d942693df17cf704797de644c5676` |
| `25-projects@1920.png` | 1920×1080 | `#/projects` | 151,384 | `fcf9a21a36f738c3eb1b2badf5c9bb61362323de71430a46d38e5ab7c8a05a0e` |
| `26-project-detail@1920.png` | 1920×1080 | `#/projects/13ec60724577474498718544c22b508b` | 244,100 | `f872acdaa7d8da497713ae6040483fb5a26042acd046f07bece30927caff8b68` |
| `27-creative-tools@1920.png` | 1920×1080 | `#/tools` | 109,022 | `467b58406981439c4c6ce968553284727057f78eb9c5d88f73b065a28fc118d3` |
| `28-deliverables@1920.png` | 1920×1080 | `#/deliverables` | 109,532 | `b7e780b2e2434e41bc42bfab4218556c7da902d910d825118d1ffa56f389ae69` |
| `29-evidence@1920.png` | 1920×1080 | `#/evidence` | 111,070 | `b562198581d84b0bdcbb364856a6ce24ce972fb12bcdf2951132b55a0a517755` |
| `30-preflight@1920.png` | 1920×1080 | `#/preflight` | 144,144 | `df0eba1d2e3a7c1a703a2b3f790342f2fffc36786de77b90433f8d7ad1d53e04` |
| `31-settings@1920.png` | 1920×1080 | `#/settings` | 244,646 | `d87f8f2ebe8b24cd363f7d0441bdfbabe194359f28728a4a8b14a3e17f76bc1f` |
| `32-dashboard@2560.png` | 2560×1440 | `#/dashboard` | 260,375 | `c42355060b72d1755f6341b9f222d46b0feb60564e325ec507de9abf3cb3e0ad` |
| `33-projects@2560.png` | 2560×1440 | `#/projects` | 170,209 | `557c47bfcc4bd51e04833538c21a34fa1934f60ba21529250fe59ab63b8f2f33` |
| `34-project-detail@2560.png` | 2560×1440 | `#/projects/13ec60724577474498718544c22b508b` | 306,958 | `121c6792109aa935e716a5bc12e0e5679baefc5d97c61249512e1b31595befb2` |
| `35-creative-tools@2560.png` | 2560×1440 | `#/tools` | 127,936 | `1484a87b0f1933a89c4d367e50d3469e0a7e3214d846fb46ae1c6f77e16e9f44` |
| `36-deliverables@2560.png` | 2560×1440 | `#/deliverables` | 128,722 | `4040e6344aa124acd092e3aab180c5a0523584e21280a01226c77a487060b510` |
| `37-evidence@2560.png` | 2560×1440 | `#/evidence` | 130,236 | `e245898c3f0b1e375bff7725e3541943cdf6640676036068767f28e28d5b2e4e` |
| `38-preflight@2560.png` | 2560×1440 | `#/preflight` | 163,108 | `2566357e31e8a0b7f4c9f14fd081eb56b588733ba65944af06985fdb4659adf6` |
| `39-settings@2560.png` | 2560×1440 | `#/settings` | 259,017 | `1cbb578aedea1145326f037e880a33ab3d776df58161ac1d5e75574c69392453` |

## 观察记录（由清单内 `rendered` 字段生成，非人工描述）

- 捕获时间 `2026-10-06T08:36:59.857Z`；commit `8167e623`；bundle `164033` 字节。

### `#/dashboard`

- 本轮 KPI 实际读数：项目=1 · 设计系统=4 · 服务状态=OK · 服务版本=0.1.0-alpha.0

- 面板标题（读回自渲染 DOM）：「仪表盘」, 「最近项目」, 「设计质量趋势 · 未读回」, 「Research」, 「Brand」, 「Delivery」, 「继续项目」, 「待审（需人工处理）（0）」, 「失败（0）」

- 质量趋势面板标题为「设计质量趋势 · 未读回」——无质量路由即无图。
- `未读回/未连接` 文案在该页出现：True。

### `#/projects/:id`

- 详情页面板标题：「Closeout 1791275795091」, 「任务台账（1）」, 「设计层契约」, 「交付包（0）」, 「简报（Brief）· 1 个版本」, 「方向（Direction）· 1 个候选」, 「设计系统（DesignSystem）· 目录 4 项 · 绑定 1 次」, 「参考素材（1）」, 「Inspector」

### 布局与溢出（来自 `ui-audit/report.json`，65 作用域）

- 横向溢出：0；触控目标 <24px：0；无可访问名控件：0；对比度失败：0；命令面板：0；measurement-invalid：0。

## 历轮截图暴露并修复的真实缺陷

- **KPI 假值**：`animateKpiCount` 用 `parseFloat` 解析 `data-count`，
  `0.1.0-alpha.0` 被当作 `0.1` 计数，服务版本卡最终渲染为 `0.1`。
  修复：仅纯数字才参与 count-up（commit `8036439`）。
- **动画中间帧**：count-up 为 JS 驱动，`animations: 'disabled'` 不生效，
  首拍把「设计系统 3」（真实为 4）写进了图里。修复：截图前等待数值稳定。
- 2026-10-06 批次（UI 审计修复，非截图驱动发现，但改变了截图内容，故一并记录）：
  移除仪表盘硬编码 72/84/65% 进度条与编造的质量趋势曲线；项目状态列 `Active` →
  `未读回`；预检词表 `PASS` → `READY`；状态药丸与主按钮改配（白字压品牌蓝实测
  1.83–4.45:1，不达 AA）；侧栏演示身份 `Alex / Personal Workspace` 改为
  「本地单用户 · 无身份路由 · 未读回」；命令面板导航修复（`#dashboard` → `#/dashboard`）。

## 诚实结论与证据等级

- 40 张 PNG（每张配 `.license` sidecar）为真实 Chromium（149.0.7827.55，`chromium-1228/chrome-win64/chrome.exe`，
  非 headless-shell）渲染，绑定 exact commit `ca67834a`、bundle 163269 字节 SHA-256 `3f060019…`、
  服务端口与时间戳；**E1 结构 + E2 受控运行时**级视觉证据。
- **不是 E3**：未驱动 Photoshop/Illustrator，未产出原生可编辑设计文件。
- **不是 E4**：无人工视觉验收；本文件不含任何「已验收」判定。
- 截图只证明 UI 在 5 档视口下正常渲染并读回真实服务状态。
