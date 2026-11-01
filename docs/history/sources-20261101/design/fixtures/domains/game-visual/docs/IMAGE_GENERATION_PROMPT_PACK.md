# MINIGAME 图像生成 Prompt Pack

> 目标：把当前项目视觉从“AI 感 UI / 网页表单 / 假监控画面”拉回到 **真实 CCTV 监控终端 + 恐怖夜班控制台 + 可读移动游戏 HUD**。
>
> 生成图只负责真实感、材质、监控背景和 UI 参考；不要让模型生成可读文字。游戏里的中文、按钮、日志和数值由代码/CSS 叠加。

## 0. 使用原则

- 图片负责真实感：CCTV 画面、控制台材质、玻璃、噪声、灯光。
- 代码负责文字：标题、按钮文案、日志、数值、状态。
- CSS/HUD 负责交互：点击区域、布局、响应式、安全区。
- 每张图都要明确要求：**No readable text / no logo / no watermark / no UI text**。
- 优先生成真实低清摄像头素材，不要生成完整花哨网页。

## 1. 全局英文风格前缀

把下面这段加到所有生成任务前面：

```text
Photorealistic mobile game visual assets for a horror anomaly surveillance control console. Real CCTV security camera footage style, low-resolution analog surveillance feed, green night vision tint, dirty lens, compression artifacts, subtle scanlines, emergency lighting, grimy industrial surfaces, realistic shadows, no fantasy, no cartoon, no anime, no glossy sci-fi, no clean corporate dashboard. The mood is tense, realistic, found-footage, night shift control room, old security monitor, CCTV matrix, emergency console, analog signal interference. No readable text, no logos, no watermark, no UI buttons, no fake language, no characters facing camera.
```

## 2. 全局 Negative Prompt

```text
text, readable text, watermark, logo, signature, UI text, buttons, fake letters, gibberish, anime, cartoon, illustration, cute, colorful, clean corporate UI, glossy futuristic sci-fi, neon cyberpunk city, overdesigned dashboard, floating holograms, 3D render, plastic surfaces, perfect symmetry, smiling people, gore, blood, monster, fantasy creature, obvious AI artifacts, distorted hands, extra limbs
```

中文版本：

```text
不要文字，不要水印，不要按钮，不要乱码，不要商标，不要二次元，不要卡通，不要干净的企业后台，不要科幻全息屏，不要赛博朋克城市，不要怪物，不要血腥，不要人物正脸，不要 AI 感畸形结构。
```

## 3. 推荐规格

| 用途 | 比例 | 建议尺寸 |
| --- | --- | --- |
| 游戏主背景 / UI 参考 | 9:16 | 1080x1920 / 1440x2560 |
| CCTV 主监控画面 | 16:9 | 1280x720 / 1920x1080 |
| 小监控窗口 | 4:3 | 1024x768 |
| 噪声 / 撕裂 / 材质叠层 | 16:9 或 9:16 | 尽量高分辨率，支持透明 PNG 更好 |

## 4. 当前最需要生成的三张

### A. 默认监控画面：地下货梯 / 电梯入口 CCTV

```text
Photorealistic CCTV security camera still of an old basement freight elevator entrance at night. Dirty concrete corridor, industrial service elevator doors, dim fluorescent emergency lights, green night vision tint, fixed high corner security camera perspective, wide angle lens distortion, low resolution analog CCTV quality, compression artifacts, scanlines, dust on lens, dark vignette, damp floor reflections, peeling paint, utility pipes, abandoned but believable. No readable text, no signs with legible letters, no logos, no watermark, no UI, no people, no monsters, no blood.
```

### B. 整体 UI 重设计参考图

```text
A complete vertical mobile game screen mockup for a horror anomaly CCTV control console, 9:16 portrait layout. The screen looks like a real night shift surveillance terminal, not a website and not a form. Top area has compact emergency status header and timer. Middle area has a large realistic CCTV monitor showing a grimy service elevator corridor at night, with scanlines, lens distortion, compression noise, multi-camera thumbnails and analog interference. Lower area has tactile physical console buttons, emergency stop button, metal panels, glowing status strips. Bottom area has a terminal log panel. Dark teal black palette, green night vision, red emergency accents, amber warning highlights, dirty glass, realistic hardware, premium horror mobile game UI. No readable text, no logos, no watermark, no fake letters, no people.
```

### C. 控制台按钮区

```text
Photorealistic close-up of an old emergency control console panel for a night shift surveillance game. Dark worn metal surface, six large tactile rectangular buttons, emergency stop button, small indicator lights, scratched acrylic covers, glowing green and amber LEDs, dust, fingerprints, old labels blurred and unreadable, industrial hardware, realistic shadows, mobile game asset, top-down slight perspective. No readable text, no logos, no watermark, no hands, no people.
```

## 5. 完整主界面视觉基准图

用于生成一张“最终游戏应该长什么样”的参考图。允许出现 UI 结构，但不要可读文字。

```text
A complete vertical mobile game screen mockup for a horror anomaly CCTV control console, 9:16 portrait layout.

The screen shows a realistic night shift surveillance terminal, not a website and not a form. Top area: compact emergency status header with timer module, warning lights, small signal indicators, dark glass panels. Middle area: large CCTV monitor feed showing a grimy service elevator corridor at night, green monochrome security camera footage, scanlines, lens distortion, compression noise, small multi-camera thumbnails, red recording dot, analog interference. Left and right edges: dense but readable industrial HUD widgets, power meter, stability meter, anomaly level meter, emergency bus indicators. Lower area: tactile physical control console with six large game-like buttons, metal panels, labels are blank or unreadable, glowing status strips, warning bezels. Bottom area: terminal log panel with dark glass and subtle green lines, no readable text.

Visual style: realistic hardware console, dirty glass, dark teal and black palette, emergency red accents, amber warning highlights, believable mobile game UI, premium horror game interface, high contrast, cinematic lighting, tactile buttons, not a flat web dashboard.

No readable text, no logos, no watermark, no fake letters, no people, no monsters, no anime, no cartoon.
```

## 6. 各皮肤 CCTV 主图 Prompts

### 6.1 默认 / 电梯 / 地下货梯

```text
Photorealistic CCTV security camera still of an old basement freight elevator entrance at night. A dirty concrete corridor, industrial service elevator doors, dim fluorescent emergency lights, green night vision tint, fixed high corner security camera perspective, wide angle lens distortion, low resolution analog CCTV quality, compression artifacts, scanlines, dust on lens, subtle dark vignette, damp floor reflections, peeling paint, utility pipes, warning tape, abandoned but believable. The image should look like real surveillance footage from a cheap security camera, not concept art. No readable text, no signs with legible letters, no logos, no watermark, no UI, no people, no monsters, no blood.
```

### 6.2 医院病区

```text
Photorealistic CCTV security camera still of an empty hospital ward corridor at 3 AM. A dark hospital corridor with closed patient room doors, nurse station far in the background, weak green emergency lighting, old ceiling security camera angle, realistic low-resolution surveillance footage, analog noise, compression artifacts, fluorescent flicker, reflective floor, medical equipment silhouettes, privacy curtains, cold sterile atmosphere, subtle horror tension. No readable text, no hospital logo, no watermark, no UI overlay, no people, no blood, no gore, no monster, no fake letters.
```

### 6.3 安防室 / 监控中心

```text
Photorealistic CCTV view of an empty security control room at night. Multiple old monitors on a desk, dark room, green and blue monitor glow, analog surveillance equipment, empty chair, coffee cup, tangled cables, dusty keyboard, emergency red light reflection, realistic low light photography, cheap CCTV lens, subtle noise, gritty found footage feel. No readable text, no logos, no UI buttons, no people, no watermark, no fake letters.
```

### 6.4 工厂控制区

```text
Photorealistic CCTV security camera still of an abandoned factory control bay at night. Industrial machinery, conveyor belts stopped, warning lights dimly blinking, concrete floor, metal railings, pipes, steam haze, green security camera night vision, low resolution analog footage, lens distortion, scanlines, compression artifacts, realistic surveillance camera perspective from high corner. No readable text, no logos, no people, no monsters, no blood, no UI.
```

### 6.5 地铁末班站台

```text
Photorealistic CCTV security camera still of an empty subway platform after midnight. A deserted underground train platform, closed platform screen doors, dim green fluorescent lights, tunnel darkness, security camera high angle, low resolution surveillance footage, compression artifacts, scanlines, dirty lens, reflective tiles, emergency light glow, realistic urban transit CCTV atmosphere. No readable text, no station name, no logos, no advertisements, no people, no train driver, no UI, no watermark.
```

### 6.6 无人酒店前台

```text
Photorealistic CCTV security camera still of an empty hotel lobby reception desk at midnight. Dark front desk, old key cards, dim warm emergency lights, corridor to elevators in background, security camera high corner view, low-resolution CCTV footage, analog noise, compression artifacts, greenish tint, reflective marble floor, abandoned night shift atmosphere, subtle horror tension. No readable text, no hotel logo, no people, no watermark, no UI, no fake letters.
```

## 7. UI / 材质 / 叠层 Prompts

### 7.1 控制台实体面板

```text
Photorealistic close-up of an old emergency control console panel for a night shift surveillance game. Dark worn metal surface, six large tactile rectangular buttons, emergency stop button, small indicator lights, scratched acrylic covers, glowing green and amber LEDs, dust, fingerprints, old labels intentionally blurred and unreadable, industrial hardware, realistic shadows, cinematic but grounded, mobile game asset, top-down slight perspective. No readable text, no logos, no watermark, no hands, no people.
```

### 7.2 HUD 玻璃面板材质

```text
Dark transparent glass HUD panel texture for a horror surveillance console game. Black teal tinted glass, subtle scratches, fingerprints, dust, faint scanlines, soft green glow on edges, red emergency reflection, old monitor bloom, realistic acrylic surface, no text, no icons, no buttons, transparent-like dark panel, high resolution texture. No readable text, no logo, no watermark.
```

### 7.3 监控噪声叠层

```text
Analog CCTV interference overlay texture. Fine scanlines, VHS tracking noise, compression blocks, static snow, faint rolling horizontal distortion, green monochrome tint, dirty lens specks, dark vignette, old surveillance camera artifacts, high resolution overlay, no objects, no text, no logos.
```

如果支持透明背景：

```text
transparent background PNG, white and green noise only, overlay texture
```

### 7.4 异常画面撕裂叠层

```text
CCTV signal corruption overlay for a horror surveillance game. Horizontal tearing, frozen frame glitches, analog tracking distortion, green and red channel separation, pixel compression blocks, emergency interference, VHS static, broken security feed, high contrast dark overlay, no readable text, no objects, no people, no logo.
```

### 7.5 开始页背景

```text
Vertical mobile game start screen background for a realistic horror surveillance console. A dark night shift control desk facing multiple CCTV monitors, one large monitor showing an empty elevator corridor, old keyboard, emergency phone, warning lights, green monitor glow, realistic low light photography, dirty glass, analog security equipment, tense found-footage atmosphere. Composition leaves empty dark space in the center for game title and start button overlay. No readable text, no logos, no watermark, no people, no fake UI letters.
```

### 7.6 失败页背景

```text
Vertical mobile game failure screen background for a horror CCTV control console. Dark emergency monitor room, red warning light glow, distorted CCTV screens, power failure, glass reflections, analog static, corrupted surveillance feed, realistic industrial console, tense but not bloody, premium mobile horror game atmosphere. No readable text, no UI words, no logos, no watermark, no people, no monsters.
```

## 8. 明确禁止方向

```text
Do not make it look like a web form, survey page, SaaS admin dashboard, clean data analytics dashboard, generic cyberpunk UI, colorful mobile app, cartoon game, sci-fi spaceship cockpit, flat Figma mockup, or button grid floating on plain background.
```

中文：

```text
不要像表单、调查问卷、后台管理系统、SaaS 仪表盘、普通网页、普通 App、赛博朋克全息屏、卡通游戏、科幻飞船驾驶舱。
```

## 9. 当前保留的运行时生成资产

项目清理后只保留已被 H5/CSS 实际引用的背景、纹理和干扰层：

```text
assets/generated/cctv-hospital-ward-real.png
assets/generated/cctv-security-room-real.png
assets/generated/cctv-factory-real.png
assets/generated/cctv-subway-platform-real.png
assets/generated/cctv-hotel-lobby-real.png
assets/generated/cctv-elevator-corridor-clear.png
assets/generated/cctv-elevator-corridor-figure.png
assets/generated/cctv-elevator-corridor-warp.png
assets/generated/overlay-cctv-noise.png
assets/generated/overlay-signal-tear.png
assets/generated/texture-hud-glass.png
assets/generated/texture-control-panel.png
```

## 10. 接入优先级

1. 保持当前 CCTV 状态图和运行时 HUD 为正式玩家版本。
2. `texture-control-panel.png`、`texture-hud-glass.png` 继续服务 H5 Debug Console。
3. 其它皮肤继续使用各自已接线的背景。
4. 异常态叠层继续使用 `overlay-cctv-noise.png`、`overlay-signal-tear.png`。

## 11. 验收标准

生成图进入游戏后，至少要满足：

- 一眼看上去像真实监控，不像 AI 插画。
- 没有乱码文字、水印、Logo。
- 监控图不要抢走交互文字可读性。
- 主界面不像表单/后台，像游戏控制台/HUD。
- 雷电模拟器上按钮可点，`game_start` 能触发。
- Android WebView assets 打包包含图片。
