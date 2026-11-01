# Tauri 前端设计系统套用（validated 2026-08-14）

WORK-LAB Observer 前端"配色太难看 → 套成熟模板"的结论 + 可复用配方。用户对"乱/塌陷"之外的第二个强诉求是**配色/质感**，且明确要求"多套几个牛逼的模板"（高仿网上高星项目）而非在原设计上打补丁。

## 核心教训：Apple Liquid Glass 在 Windows WebView2 上翻车

原前端用 Apple Liquid Glass 风格：Tauri 窗口 `transparent: true` + body `background: transparent` + 卡片 `rgba` 半透明 + `backdrop-filter: blur(...)`。在 Windows WebView2 上：

- 透明窗口 + backdrop-filter 的毛玻璃**不生效**（WebView2 对透明窗口的 backdrop blur 支持缺失/有限）。
- 结果：半透明 rgba 卡片没有模糊背景，内容直接透出（桌面/背后窗口/卡片互相透出）→ 视觉上"乱、糊、重叠"，即使布局 span/宽度数值全对，用户看到的还是乱的。

**修复方向：放弃玻璃，用实色。** Linear / Vercel / Apple 官网的深色都是**不透明背景 + 实色卡片 + 细边框**，玻璃只用于悬浮导航（且在不透明内容上方）。套模板时：
- `--wl-canvas` 用实色（不要 transparent）
- 卡片 surface 用实色 hex/rgba（不要依赖 backdrop blur）
- **删除 `.wl-card` / `.wl-shell` 的 `backdrop-filter`**（实色背景上 blur 无意义，且是浑浊来源）

## 套模板配方：dark=Linear，light=Vercel（双主题切换）

一个 tokens.css 里两套主题：`[data-theme="dark"]` 用 Linear、`[data-theme="light"]` 用 Vercel，前端 `?theme=` 或顶栏按钮切换即可让用户看到两种成熟风格。

### Linear 深色（developer-tool 仪表盘，用户偏好）

```css
--wl-canvas: #08090a;              /* marketing black 近黑，非纯黑 */
--wl-blue: #5e6ad2;                /* brand indigo 唯一强调色 */
--wl-green: #10b981;               /* emerald 状态 */
--wl-purple: #7170ff;              /* accent violet */
--wl-shell: #0f1011;               /* panel dark 实色 */
--wl-sidebar: #0f1011;
--wl-surface-1: #191a1b;           /* Level 3 */
--wl-surface-2: #23252a;
--wl-surface-3: #28282c;
--wl-surface-hover: #2a2a2e;
--wl-border-subtle: rgba(255,255,255,0.05);   /* 半透明白细边框 */
--wl-border-strong: rgba(255,255,255,0.08);
--wl-text-primary: #f7f8f8;        /* 近白，非 #ffffff */
--wl-text-secondary: #d0d6e0;
--wl-text-muted: #8a8f98;
--wl-focus: #7170ff;
--wl-radius-sm/md/lg/control: 6px/8px/8px/6px;  /* 精密小圆角，非 20px 大圆角 */
--wl-radius-shell: 12px;
--wl-shadow-card: 0 0 0 1px rgba(255,255,255,0.05), 0 1px 2px rgba(0,0,0,0.2);
```

要点：单一 indigo 强调色（不要 6 种杂色）；文字 `#f7f8f8` 非纯白；边框半透明白 0.05–0.08；6–8px 精密圆角；阴影用 ring（`0 0 0 1px`）而非大模糊阴影。

### Vercel 浅色

```css
--wl-canvas: #ffffff;
--wl-shell/sidebar: #fafafa;
--wl-surface-1: #ffffff;
--wl-surface-2: #fafafa;
--wl-surface-3: #f5f5f5;
--wl-border-subtle: rgba(0,0,0,0.08);   /* shadow-as-border */
--wl-border-strong: rgba(0,0,0,0.12);
--wl-text-primary: #171717;             /* 近黑，非 #000000 */
--wl-text-secondary: #4d4d4d;
--wl-text-muted: #666666;
--wl-focus: #0072f5;
--wl-shadow-card: rgba(0,0,0,0.08) 0 0 0 1px, rgba(0,0,0,0.04) 0 2px 2px;
```

### 模板选择映射（popular-web-designs 的 templates/*.md）

| 需求 | 模板 |
|---|---|
| 深色 dev-tool 仪表盘（用户偏好） | linear.app.md |
| 浅色克制精确 | vercel.md |
| 数据密集深色仪表盘 | sentry.md |
| 深色 emerald dev-tool | supabase.md |
| 苹果官网质感 | apple.md |

套模板 = `skill_view(name="popular-web-designs", file_path="templates/<site>.md")` 拿 token → 替换 tokens.css 的配色变量 + 圆角 + 阴影 → **删除 backdrop-filter** → 重新 `cargo tauri build --no-bundle`。

## 一次做多个主题让用户选

用户说"多套几个模板"时，不要只做一个。用 `data-theme` 双主题（dark + light）承载两套成熟设计系统，让用户切换对比，而不是让用户等下一轮再改。
