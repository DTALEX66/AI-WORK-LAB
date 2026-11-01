# DESIGN-LAB UI R2 · 可实施方案与前端任务包

版本：UI-20261009-r2。R2 优先覆盖 R1 的导航、目录、详情呈现、输入与目标、成果检索和响应式布局；其余制作、核验、评审、交付、反馈及连接页面保留 R1 语义。此包交付前端实施参考，没有接通实际软件、知识服务或生产后端。

建议阅读顺序：

1. `specs/01_UI_SCHEME.md`：方案、导航、页面与状态规则。
2. `AGENT_START.md`：执行边界、实现顺序与交付要求。
3. `specs/navigation.json`、`specs/design_tokens.json`、`specs/implementation_tasks.json`：配置与任务映射。
4. `screens/`：21 张效果图与 1 张总览，含 4K 首屏、完整长页、手机、平板与浅色主题。
5. `assets/art/`：14 张独立 SVG + 对应 3840 × 2400 PNG；优先使用 SVG。
6. `contracts/` 与 `specs/r1/`：保留的语义契约及细节；不是已经存在的接口。

## 预览

在本包根目录运行：

```sh
python3 -m http.server 8000
```

访问 `http://localhost:8000/prototype/index.html`。默认目录是能力资产；`#input` 为跨领域制作输入。原型无外部请求，浏览器本地草稿不向服务提交。知识、宿主和正式交付均未连接。上方“查看品牌演示流程”进入继承的品牌海报演示，不会根据新输入执行分析。

`prototype/app.js` 是 R1 基线，`r2.js` 为增量覆盖，`r2.css` 为增量样式。生产需在实际框架中整合成组件，不应把这两个版本一直并排维护。字体及其声明在 `assets/fonts/`。

## 重建与验收

```sh
python3 scripts/build_art_r1.py
python3 scripts/build_art.py
node scripts/verify.mjs
python3 scripts/build_specs.py
```

验收脚本需要 Node 与 Playwright；安装方式按目标仓库工具链执行。已安装浏览器可用环境变量 `UI_CHROMIUM_PATH` 指定；否则使用 Playwright 管理的 Chromium。脚本使用临时本地 HTTP 服务，不连接任何真实业务端点。重跑会刷新效果图、4 个新增素材 PNG 和 `evidence/verification.json`。

`evidence/verification.json` 是本包参考 UI 的实际检查结果；不代表业务接口、真实软件执行、真人评审或无障碍认证已通过。`SHA256SUMS.txt` 用于核对包内文件完整性。
