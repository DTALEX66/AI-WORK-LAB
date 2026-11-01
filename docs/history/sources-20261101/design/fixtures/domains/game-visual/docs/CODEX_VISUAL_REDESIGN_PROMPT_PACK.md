# Codex 视觉重构完整提示词包：异常电梯 CCTV GIF 游戏 HUD

> 用途：把本文件完整交给 Codex / 其他代码智能体，让它在当前 MINIGAME 项目里执行一轮视觉重构。
>
> 目标：从“网页式 HUD / 控制台面板”进一步升级为“真实监控恐怖游戏 UI”，主视觉必须是 CCTV GIF，操作必须像真实电梯硬件按钮。

---

## 0. 一句话总指令

```text
把当前 MINIGAME UI 重构成真实监控恐怖游戏 HUD：参考 Five Nights at Freddy’s / I’m on Observation Duty / Observation / Not For Broadcast。主视觉必须是 assets/generated/elevator-cctv-loop.gif 的 CCTV GIF，占 65%-75% 面积；下方是实体电梯硬件控制台按钮；状态改成短码 telemetry chips；接管条改为非覆盖式底部授权条；移动竖屏顺序为 CCTV -> controls -> telemetry -> logs -> override。不要网页菜单、不要大段文字、不要表格式 dashboard。补测试，跑 npm test 和 npm run verify:summary，并做浏览器视觉验收。
```

---

## 1. 背景与参考游戏

当前项目是 H5 / Android WebView 小游戏《异常电梯控制台》。玩法核心是：

```text
玩家扮演夜班电梯监控员，通过 CCTV 观察异常，按电梯控制键处理事件，在倒计时内避免系统崩溃。
```

这次不要继续做成普通网页 dashboard。要对齐真实游戏 UI 语言。

### 1.1 Five Nights at Freddy’s 参考点

关键词：

```text
night security guard
surveillance camera
limited power
door control
survival horror
point-and-click
low fidelity security UI
```

可借鉴：

- 玩家身份是值班员。
- 摄像头/门/电力是生死资源。
- UI 不是漂亮网页，而是低保真、压迫、噪声重、信息极少。
- 关键交互很少，但每个按钮都有重量。

### 1.2 I’m on Observation Duty 参考点

关键词：

```text
monitor live surveillance camera footage
spot anomalies
survive the night shift
camera room switching
minimal explanation
```

可借鉴：

- 大面积 CCTV 是玩法本体。
- 玩家靠观察发现异常变化。
- UI 少解释，画面承担主要信息。
- 异常不是抽象图标，而是发生在监控画面里。

### 1.3 Observation 参考点

关键词：

```text
diegetic terminal UI
AI operating system
space station monitoring
system nodes
signal state
module interface
```

可借鉴：

- UI 像真实设备/系统界面，不像网页。
- 系统状态、信号、节点、摄像头信息叠在画面上。
- 冷静、工业、压抑。

### 1.4 Not For Broadcast 参考点

关键词：

```text
broadcast control room
multi-screen video feeds
hardware switcher
preview/program monitor
red emergency controls
```

可借鉴：

- 主屏 + 小屏阵列。
- 视频信号源切换。
- 硬件按钮和控制台感。
- 红色紧急按钮拥有最高视觉权重。

---

## 2. 最终视觉方向

不要再做：

```text
左侧菜单 + 右侧画面 + 表格式状态 + 普通网页按钮
```

要做成：

```text
一台老旧电梯监控控制台。
主屏播放 CCTV GIF。
下方是一排真实电梯控制键。
周围只有极少状态灯、短码、倒计时和日志 ticker。
玩家像在操作一台真实设备。
```

核心视觉判断标准：

```text
第一眼看到的是 CCTV GIF，不是菜单。
第二眼看到的是电梯硬件按钮，不是网页按钮。
第三眼看到的是倒计时、电力、异常等级，不是说明文字。
```

---

## 3. 视觉关键词词库

### 3.1 总体 UI 关键词

```text
surveillance horror game UI
diegetic control panel
analog CCTV monitor
security-room interface
low fidelity camera feed
degraded signal
scanline noise
VHS static
red REC indicator
timecode overlay
emergency hardware controls
tactile elevator keycaps
warning LEDs
dark industrial console
amber/red danger accent
minimal text HUD
camera switching thumbnails
anomaly detection corners
monitor-first composition
```

### 3.2 氛围关键词

```text
oppressive
industrial
low fidelity
analog
found footage
night shift
security room
basement elevator
degraded camera feed
signal tearing
CRT glass
dirty control panel
scratched metal
emergency lighting
```

### 3.3 禁止方向

```text
no SaaS dashboard
no admin panel
no form UI
no survey-like layout
no large menu cards
no onboarding checklist
no abstract scanner icon
no clean cyberpunk neon overload
no generic web buttons
no long paragraphs
no table-like status panel
```

---

## 4. 桌面 / 横屏布局规范

### 4.1 主布局

使用 `main CCTV + hardware console + thin telemetry rail`。

推荐布局比例：

```text
CCTV monitor: 65% ~ 75% visual weight
support rail / telemetry: 15% ~ 25%
hardware console: bottom strip, high interaction weight
logs: low-height ticker, not a text wall
```

推荐结构：

```text
┌──────────────────────────────────────────────┐
│ NIGHT SHIFT   TIMER 60   PWR 100   SYS OK    │  top compact status
├───────────────┬──────────────────────────────┤
│ telemetry     │                              │
│ chips         │                              │
│               │       MAIN CCTV GIF          │
│ small log     │       REC / CAM / HUD        │
│               │                              │
├───────────────┴──────────────────────────────┤
│       HARDWARE ELEVATOR CONTROL KEYPAD        │
├──────────────────────────────────────────────┤
│ LOG TICKER                         OVERRIDE   │
└──────────────────────────────────────────────┘
```

或者更游戏化：

```text
┌──────────────────────────────────────────────┐
│ TIMER 60                         SYSTEM OK    │
├──────────────────────────────┬───────────────┤
│                              │ CAM-01        │
│                              │ CAM-07        │
│        MAIN CCTV GIF         │ THERM         │
│                              │               │
│                              │ telemetry     │
├──────────────────────────────┴───────────────┤
│ OPEN CLOSE UP DOWN STOP RESET LOG             │
└──────────────────────────────────────────────┘
```

### 4.2 CCTV 主屏

必须是主视觉。

要求：

- 使用 GIF / animated image / video。
- 路径优先：

```text
assets/generated/elevator-cctv-loop.gif
```

- 如果 GIF 不存在，先保留 fallback：
  - 尝试加载 GIF。
  - 加载失败时回退现有 PNG + CSS 动画层。
- CCTV 画面上叠 HUD，不要用旁边长文字解释。

CCTV 必备叠层：

```text
CAM-03
REC red dot
23:59:47 timecode
SYSTEM: STABLE / UNSTABLE / CORRUPTED
THREAT: 0-5
subtle scanlines
noise texture
signal tearing
red detection corners
```

CCTV 内异常必须嵌入画面：

```text
门缝红光
远处黑影
断续热源残影
画面撕裂
检测框轻微闪烁
```

禁止：

```text
居中抽象雷达
黄色点 + 红柱子
漂浮红点
与底图不对应的红线
大号说明文字
```

### 4.3 摄像头小屏

可放在 CCTV 右侧或下方。

数量：3 个即可。

```text
CAM-01
CAM-07
THERM
```

要求：

- 小屏只做氛围和系统感。
- 不要抢主 CCTV。
- 小屏可以用静态暗图、噪声、低透明缩略图。

---

## 5. 硬件电梯控制台规范

### 5.1 操作键

当前动作映射：

```text
openDoor        开门      ◀▯▶
closeDoor       关门      ▶▯◀
moveUp          上行      ▲
moveDown        下行      ▼
emergencyStop   急停      STOP
restartSystem   重启      ↻
inspectLog      日志      LOG
unlockHiddenLog 解码      DEC
```

按钮必须像真实硬件：

```text
bevel
inset shadow
pressed state
LED indicator
metal/plastic texture
tactile border
short label
icon first
```

禁止：

```text
普通 button 样式
大面积渐变卡片
网页 CTA 风格
长文案按钮
```

### 5.2 急停按钮

急停必须是最高权重按钮。

要求：

```text
red / amber danger color
round or large rectangular emergency button
stronger shadow
larger visual weight
label: STOP / 急停
```

不要和普通按钮同级。

### 5.3 按钮布局

桌面：

```text
OPEN CLOSE UP DOWN STOP RESET LOG DEC
```

移动端：

```text
4 列 keycap grid
每个按钮 min-height >= 48px
```

---

## 6. 状态信息规范

状态不要像表格，也不要长中文标题。

使用短码 telemetry chips：

```text
F 01
DOOR CLOSED
PAX 1
PWR 100
STB 100
ANOM 0
```

或者中英混合短码：

```text
F 01
门 关
客 1
电 100
稳 100
异 0
```

优先级：

```text
critical: floor, door, passengers, power, stability
danger: anomalyLevel
secondary: reviveCount, decodeCount, hiddenLogs
```

要求：

- critical 高对比。
- danger 红色/琥珀色。
- secondary 降透明度或收进日志。
- 不要 10 个同权重卡片。
- 不要大标题“电梯状态 / 操作面板 / 系统日志”抢戏，可改短码：

```text
STATUS
CTRL
LOG
SYS
```

---

## 7. 接管 / OVERRIDE 规范

不要大弹窗。

不要遮挡 CCTV。

不要 checklist。

不要规则说明。

使用非覆盖式底部授权条：

```text
接管电梯        OVERRIDE
```

要求：

```text
height: 44px ~ 56px
position: static 或文档流布局
不 fixed 覆盖底部按钮
不盖住日志
不盖住状态 rail
```

可以作为页面底部/控制台底部一条低亮硬件状态条。

---

## 8. 移动竖屏规范

移动端优先级非常重要。

顺序必须是：

```text
1. 顶部紧凑状态条
2. 主 CCTV GIF
3. 电梯硬件控制键
4. 关键状态 chips
5. 短日志 ticker
6. OVERRIDE 授权条
```

CSS 方向：

```css
@media (max-width: 700px) and (orientation: portrait) {
  html, body {
    height: auto;
    min-height: 100dvh;
    overflow-x: hidden;
    overflow-y: auto;
  }

  .console-shell {
    height: auto;
    min-height: 100dvh;
    overflow: visible;
  }

  .grid {
    grid-template-areas:
      "monitor"
      "actions"
      "status"
      "logs";
  }

  .actions {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .handoff-strip,
  .start-overlay {
    position: static;
  }
}
```

移动端验收：

```text
390x844 竖屏下，首屏必须看到 CCTV 和操作按钮。
页面允许滚动。
OVERRIDE 不覆盖底部内容。
按钮可点击。
CCTV 不被压扁。
```

---

## 9. GIF 监控生成词

如果需要先生成 GIF，用这个提示词。

```text
Create a short looping animated CCTV GIF for a horror elevator control game.

Scene:
A realistic old apartment basement elevator hallway seen through a fixed security camera. The camera is mounted high in a dark corner, looking toward closed elevator doors. The environment is dirty, industrial, dim, slightly green-tinted night vision, with concrete walls, old metal elevator doors, faint emergency lighting, and a wet reflective floor.

Animation:
3 to 5 second seamless loop.
Subtle CCTV motion only, no cinematic camera movement.
Add VHS scanlines, analog noise, compression artifacts, timecode flicker, very slight signal tearing.
A thin red glow pulses from the vertical gap between the elevator doors.
A faint human-like shadow appears for a few frames near the back wall, then disappears.
A broken thermal ghost shimmer flickers near the door centerline.
Red detection corner brackets blink subtly around the anomaly target.
REC red dot flickers.
Do not include readable text except generic camera HUD if necessary.

Style:
Realistic security camera footage, low fidelity, surveillance horror, analog CCTV, not polished sci-fi, not neon cyberpunk, not cartoon, not abstract scanner UI.
Dark, oppressive, believable, like found footage from a building security room.

Output:
Looping GIF, 16:9, usable as main CCTV monitor background in a mobile HTML5 game.
```

### 9.1 中文版 GIF 生成词

```text
生成一个恐怖电梯监控游戏用的短循环 CCTV 动图 GIF。

场景：
老旧公寓地下室的电梯走廊，固定安防摄像头视角，摄像头安装在高处角落，看向关闭的金属电梯门。环境真实、肮脏、工业感、昏暗，带轻微绿色夜视色调。混凝土墙面，旧金属电梯门，微弱应急灯，地面有轻微潮湿反光。

动画：
3 到 5 秒无缝循环。
只允许轻微监控画面抖动，不要电影镜头运动。
加入 VHS 扫描线、模拟噪声、压缩伪影、时间码闪烁、轻微信号撕裂。
电梯门缝中有一条细红光缓慢脉冲。
远处墙边有模糊人形黑影闪现几帧后消失。
门缝中心附近有破碎热源残影闪烁。
异常目标周围有红色检测角标轻微闪烁。
REC 红点闪烁。
不要出现可读文字，除非是极简摄像头 HUD。

风格：
真实安防摄像头录像，低保真，监控恐怖，模拟 CCTV，不要精致科幻，不要赛博霓虹，不要卡通，不要抽象扫描仪界面。
黑暗、压抑、可信，像楼宇保安室里发现的录像。

输出：
16:9 循环 GIF，可作为移动 HTML5 游戏主监控画面背景。
```

---

## 10. 静态 fallback 图生成词

如果 GIF 暂时做不出来，先生成静态图：

```text
A realistic CCTV still frame of a basement elevator hallway for a horror surveillance game. Fixed security camera angle from upper corner, closed old metal elevator doors centered, dirty concrete walls, dim greenish emergency lighting, wet reflective floor, analog CCTV noise, VHS scanlines, low resolution, dark oppressive atmosphere. A subtle red glow leaks from the vertical gap between the elevator doors. A faint ambiguous shadow is barely visible near the back wall. No readable text. 16:9.
```

---

## 11. DOM 结构建议

目标结构：

```html
<main class="game-shell" data-skin="elevator">
  <header class="top-status-bar">
    <span>NIGHT SHIFT</span>
    <strong id="remaining">60</strong>
    <span id="systemState">SYSTEM: STABLE</span>
    <span id="powerQuick">PWR 100</span>
  </header>

  <section class="main-stage">
    <section class="cctv-monitor">
      <img class="cctv-gif" src="assets/generated/elevator-cctv-loop.gif" alt="" />
      <div class="cctv-fallback"></div>
      <div class="cctv-overlay">
        <span class="cam-id">CAM-03</span>
        <span class="rec-dot">REC</span>
        <span class="timecode">23:59:47</span>
        <span id="monitorSignal">SYSTEM: STABLE</span>
        <span id="monitorThreat">THREAT: 0</span>
        <div class="door-gap-glow"></div>
        <div class="distant-shadow"></div>
        <div class="thermal-ghost"></div>
        <div class="detection-corners"></div>
      </div>
      <aside class="camera-thumbnails">
        <button>CAM-01</button>
        <button>CAM-07</button>
        <button>THERM</button>
      </aside>
    </section>

    <aside class="support-rail">
      <div class="telemetry-chip critical">F 01</div>
      <div class="telemetry-chip critical">DOOR CLOSED</div>
      <div class="telemetry-chip critical">PWR 100</div>
      <div class="telemetry-chip danger">ANOM 0</div>
    </aside>
  </section>

  <section class="hardware-console">
    <div id="actions" class="elevator-keypad"></div>
  </section>

  <section class="log-ticker">
    <ol id="logs"></ol>
  </section>

  <section id="startOverlay" class="handoff-strip">
    <span>接管电梯</span>
    <button id="startButton" data-role="primary-start">OVERRIDE</button>
  </section>
</main>
```

不必一模一样，但语义和视觉层级要一致。

---

## 12. CSS 方向

### 12.1 主屏

```css
.cctv-monitor {
  position: relative;
  min-height: 560px;
  border: 1px solid rgba(97,255,190,.28);
  background: #010607;
  overflow: hidden;
  box-shadow:
    inset 0 0 60px rgba(0,0,0,.85),
    0 30px 110px rgba(0,0,0,.65);
}

.cctv-gif {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: contrast(1.08) brightness(.72) saturate(.72) hue-rotate(105deg);
}

.cctv-monitor::after {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    repeating-linear-gradient(0deg, rgba(255,255,255,.045) 0 1px, transparent 1px 4px),
    radial-gradient(circle at 50% 50%, transparent 45%, rgba(0,0,0,.62) 100%);
  mix-blend-mode: screen;
  opacity: .35;
}
```

### 12.2 硬件按钮

```css
.hardware-key {
  min-height: 58px;
  border-radius: 14px;
  border: 1px solid rgba(97,255,190,.28);
  background:
    linear-gradient(180deg, rgba(15,35,35,.95), rgba(0,8,10,.98));
  box-shadow:
    inset 0 2px 0 rgba(255,255,255,.08),
    inset 0 -5px 12px rgba(0,0,0,.56),
    0 8px 18px rgba(0,0,0,.42);
  color: #d8fff3;
}

.hardware-key:active {
  transform: translateY(2px);
  box-shadow:
    inset 0 4px 16px rgba(0,0,0,.72),
    0 2px 8px rgba(0,0,0,.3);
}

.hardware-key.danger,
.hardware-key[data-action="emergencyStop"] {
  border-color: rgba(255,77,109,.72);
  background:
    radial-gradient(circle at 50% 18%, rgba(255,209,102,.2), transparent 40%),
    linear-gradient(180deg, #5a111c, #190308);
  color: #fff1f3;
}
```

---

## 13. JS 渲染要求

在 `src/game.js` 渲染操作按钮时：

- 保留现有动作逻辑。
- 只改变 DOM class 和视觉结构。
- action button 输出：

```html
<button class="hardware-key" data-action="openDoor">
  <span class="key-led"></span>
  <span class="key-icon">◀▯▶</span>
  <span class="key-label">开门</span>
</button>
```

急停：

```html
<button class="hardware-key danger emergency-stop" data-action="emergencyStop">
  <span class="key-led"></span>
  <span class="key-icon">STOP</span>
  <span class="key-label">急停</span>
</button>
```

---

## 14. 资源接入要求

新增优先资源：

```text
assets/generated/elevator-cctv-loop.gif
```

可选资源：

```text
assets/generated/elevator-cctv-loop.webm
assets/generated/elevator-cctv-still.png
assets/generated/cctv-noise-overlay.png
assets/generated/signal-tear-overlay.png
assets/generated/control-panel-metal.png
```

接入逻辑：

```text
优先 GIF。
GIF 不存在或加载失败，则使用现有 CCTV PNG + CSS 动画层 fallback。
Android WebView assets 构建必须把 GIF 复制进去。
```

---

## 15. 合同测试要求

在 `tests/preview.test.js` 增加/更新测试，至少检查：

```text
.cctv-gif 或 [data-cctv-gif] 存在
.cctv-monitor 存在
.hardware-console 存在
.elevator-keypad 存在
.hardware-key 存在
.emergency-stop 或 data-action="emergencyStop" 有 danger 样式
.handoff-strip / start overlay 不使用 fixed 覆盖内容
移动端 grid/order 为 monitor -> actions -> status -> logs
移动端 .actions 为 repeat(4, minmax(0, 1fr))
不存在 start-checklist / start-rules / 大段目标说明
```

示例测试方向：

```js
test('CCTV GIF is the primary play surface', () => {
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
  const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
  assert.match(html, /class="cctv-gif"|data-cctv-gif/);
  assert.match(css, /\.cctv-monitor[\s\S]*min-height:\s*560px/);
  assert.match(css, /\.cctv-gif[\s\S]*object-fit:\s*cover/);
});
```

---

## 16. 验证命令

必须运行：

```bash
node --test tests/preview.test.js tests/androidWebview.test.js
npm test
npm run verify:summary
```

如果改了 Android/WebView 资源打包：

```bash
npm run android:build
npm run android:inspect
npm run android:install
```

如果设备不在线，必须明确说明：

```text
APK build OK，但 adb devices 没有在线设备，所以未安装。
```

不要假装安装成功。

---

## 17. 浏览器视觉验收要求

必须真实打开浏览器预览。

检查：

```text
第一眼是否是 CCTV GIF？
操作按钮是否像硬件电梯键？
急停是否最醒目？
状态是否短码化？
是否还有大段说明文字？
移动端 390x844 是否 CCTV + 操作按钮在首屏？
OVERRIDE 是否不覆盖底部内容？
控制台是否像游戏，不像网页 dashboard？
```

移动端检查建议：

```js
// 在浏览器里创建 390x844 iframe 进行移动布局检查
(async()=>{
  document.querySelector('#mobile-qa-frame')?.remove();
  const iframe=document.createElement('iframe');
  iframe.id='mobile-qa-frame';
  iframe.src=location.href+'&mobile-qa=1';
  Object.assign(iframe.style,{
    position:'fixed',left:'8px',top:'8px',width:'390px',height:'844px',
    zIndex:99999,border:'2px solid #61ffbe',background:'#020405'
  });
  document.body.appendChild(iframe);
})();
```

---

## 18. 最终验收标准

完成后必须满足：

```text
1. 主视觉是 CCTV GIF，而不是 CSS 假监控盒子。
2. CCTV 占据最大视觉面积。
3. 异常嵌入 CCTV 画面，不是抽象图标。
4. 电梯按钮像硬件控制台，不像网页按钮。
5. 急停按钮视觉权重最高。
6. 状态是短码 telemetry，不是表格。
7. 文字密度低，没有说明书式菜单。
8. OVERRIDE 是非覆盖式底部授权条。
9. 移动端可滚动，按钮可点，GIF 不被压扁。
10. npm test 和 verify:summary 通过。
11. 浏览器视觉验收通过。
```

---

## 19. 推荐提交信息

```text
Rebuild elevator HUD around animated CCTV feed
```

或者：

```text
Make CCTV GIF the primary game surface
```
