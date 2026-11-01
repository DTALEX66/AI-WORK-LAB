# Android APK 包装工程交接

这份说明用于下一台电脑继续在本项目目录内安装、构建、调试 Android WebView APK。

## 当前状态

当前 Android APK 包装走 WebView 方案：

- Android 工程目录：`android-webview/`
- APK 构建命令：`npm run android:build`
- APK 元数据验收：`npm run android:inspect`
- APK 输出：`android-webview/app/build/outputs/apk/debug/app-debug.apk`
- 包名：`com.dtalex.minigame`
- 应用名：`异常电梯控制台`
- 入口 Activity：`com.dtalex.minigame/.MainActivity`
- 启动图标：已配置自定义 `ic_launcher` / `ic_launcher_round`（电梯+CCTV+异常准星风格）

当前已验证：

- `npm run verify` 可一键执行完整验收：测试、微信构建、微信 strict、Android 构建、APK 元数据检查。
- `npm run release:check` 用于发布前强校验：真实 AppID、真实激励视频广告位、微信 runtime blocker、APK 元数据；当前占位配置下会故意失败，避免误发布。
- `npm test` 可在 Windows 当前 PATH 为微信开发者工具 Node 16 的情况下自动切到 Hermes Node 22，测试通过。
- `npm run android:build` 可产出 debug APK。
- `npm run android:inspect` 可用 `aapt dump badging` 验证包名、应用名、launcher icon、minSdk、targetSdk。
- APK 可安装、可启动。
- “开始接管”可点击，点击后倒计时从 60 开始下降。
- Android/H5 竖屏已压缩为一屏控制台：页面本身不再依赖下拉，日志/字幕在面板内滚动。
- 监控画面已不是纯文字：DOM 与 Canvas 运行时都绘制了 CCTV/电梯轿厢/乘客热源/楼层徽标/异常准星，文字只作为字幕。
- “触发异常测试”可进入游戏内失败弹层。
- logcat 未再出现 `SKIN_DATA is not defined`、`_getHiddenLog`、`RangeError` 等启动错误。

## 下一台电脑从零开始

### 1. 拉代码

```bash
git clone git@github.com:DTALEX66/MINIGAME.git
cd MINIGAME
```

如果已经有本地目录：

```bash
cd MINIGAME
git pull --ff-only origin main
```

### 2. 安装 Node 依赖

当前项目没有第三方 npm 依赖，但保留标准命令：

```bash
npm install
```

### 3. 准备项目内便携 Android 工具链

本项目不要求改系统环境变量；工具链默认放在项目内：

```text
.tools/
.gradle/
```

如果 `.tools/` 不存在，需要安装：

- JDK 17
- Gradle 8.10.2
- Android SDK commandline-tools
- Android SDK Platform 35
- Android Build Tools 35.0.0
- Android Platform Tools / adb

已验证可用的项目内环境变量：

```bash
export JAVA_HOME="$(pwd)/.tools/java/jdk-17"
export ANDROID_HOME="$(pwd)/.tools/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export GRADLE_USER_HOME="$(pwd)/.gradle"
export PATH="$JAVA_HOME/bin:$(pwd)/.tools/gradle/gradle-8.10.2/bin:$ANDROID_HOME/platform-tools:$PATH"
```

> 注意：`.tools/` 和 `.gradle/` 已在 `.gitignore`，不会上传到仓库。下一台电脑如果没有工具链，需要重新安装或复制 `.tools/`。

### 4. 构建 APK

```bash
npm run android:build
```

成功后产物：

```text
android-webview/app/build/outputs/apk/debug/app-debug.apk
```

### 5. 验证 APK 元数据

```bash
npm run android:inspect
```

应看到类似输出：

```text
[apk-check] PASS: package is com.dtalex.minigame
[apk-check] PASS: label is 异常电梯控制台
[apk-check] PASS: launcher icon is branded ic_launcher resource
[apk-check] PASS: min sdk is 23
[apk-check] PASS: target sdk is 35
[apk-check] OK
```

### 5.1 发布前私有配置（不要提交真实值）

仓库只提交安全占位值。真实 AppID / 激励视频广告位请放在本地私有文件：

```bash
cp release.config.example.json release.config.json
```

然后编辑 `release.config.json`：

```json
{
  "wechat": {
    "appid": "真实微信小游戏 AppID",
    "projectname": "MINIGAME"
  },
  "adUnits": {
    "revive": "真实复活广告位",
    "decode": "真实日志解锁广告位",
    "truth": "真实真相提示广告位"
  }
}
```

注意：

- `release.config.json` 已加入 `.gitignore`，不要提交。
- `node build.js wechat` 检测到 `release.config.json` 后，会把广告位注入生成的 `wechat-minigame/game.js`，并生成本地私有 `wechat-minigame/project.private.config.json`。
- `wechat-minigame/project.private.config.json` 也已加入 `.gitignore`，用于微信开发者工具本地识别 AppID。
- 源码 `src/gameConfig.js` 继续保留安全占位值，避免误泄露真实广告位。
- 发布前运行：

```bash
npm run release:check
```

当前仓库默认占位配置下，这个命令应该失败；填入真实私有配置后才应该通过。

### 6. 安装到雷电模拟器或小米手机

先确认设备：

```bash
adb devices -l
```

如果是雷电模拟器，常见连接端口可尝试：

```bash
adb connect 127.0.0.1:5555
adb connect 127.0.0.1:5554
adb connect 127.0.0.1:62001
adb connect 127.0.0.1:7555
adb devices -l
```

安装：

```bash
npm run android:install
```

或手动执行：

```bash
adb install -r android-webview/app/build/outputs/apk/debug/app-debug.apk
```

启动：

```bash
adb shell am start -n com.dtalex.minigame/.MainActivity
```

如果需要强制重启应用：

```bash
adb shell am force-stop com.dtalex.minigame
adb shell am start -n com.dtalex.minigame/.MainActivity
```

### 7. 调试 logcat

Android WebView 的 JS console 已接入 logcat，tag 是：

```text
MINIGAME_WEBVIEW
```

查看错误：

```bash
adb logcat -d -t 300 | grep -iE 'MINIGAME_WEBVIEW|Uncaught|ReferenceError|TypeError|RangeError|FATAL'
```

清空日志后重测：

```bash
adb logcat -c
adb shell am force-stop com.dtalex.minigame
adb shell am start -n com.dtalex.minigame/.MainActivity
```

### 8. 推荐验收路径

1. 启动 APK。
2. 确认桌面/启动器显示应用名“异常电梯控制台”和定制图标。
3. 确认首屏不是黑屏/白屏，显示“等待接管异常电梯”。
4. 点击“开始接管”。
5. 确认倒计时从 60 下降。
6. 确认主游戏竖屏一页内可见，不需要拖动整页才能玩。
7. 确认监控画面有视觉化 CCTV/电梯画面：电梯轿厢、乘客热源、楼层标记、异常准星；文字只是下方字幕。
8. 点击：
   - 开门
   - 关门
   - 上行
   - 下行
   - 急停
   - 系统重启
   - 查看日志
9. 点击“触发异常测试”。
10. 确认异常/失败弹层是游戏内 UI，不是 Android 崩溃。
11. 点击“观看广告复活”，确认模拟广告路径可用。

## 当前已修过的 APK 启动/体验问题

### 问题 1：开始接管没反应

实际根因不是触摸坐标，而是 Android bundle 初始化失败，导致按钮事件没有绑定。

已修复：

- `build.js` 正确把 `SKIN_DATA` 映射到 `__SKIN_DATA__`。
- `build.js` 正确处理 `getHiddenLog as _getHiddenLog` alias。
- `src/game.js` 增加 `bindPress()`，同时绑定 `click` / `touchend` / `pointerup`。
- `MainActivity.java` 接入 WebView console 到 logcat。

### 问题 2：修复 SKIN_DATA 后出现递归爆栈

错误：

```text
Uncaught RangeError: Maximum call stack size exceeded
```

原因：打包器把兼容 wrapper 替换成递归调用。

已修复：构建时移除该 wrapper，并直接使用 skinManager 的 `getHiddenLog`。

### 问题 3：安装包打开后竖屏一页看不全

已修复：

- Android/H5 portrait 使用固定 `100dvh` 控制台布局。
- 页面级滚动关闭，避免玩家必须上下拖动整页。
- 监控、操作、状态、日志在一屏内排列。
- 字幕/日志在各自面板内滚动。

### 问题 4：监控画面只有文字，缺少真实感

已修复：

- DOM 版监控面板加入 CCTV 视觉层。
- Canvas 小游戏版也加入 `drawCctvScene()`。
- 监控画面包含电梯井、电梯门、乘客热源、楼层徽标、异常准星、扫描线。
- 原监控文本改为字幕，不再覆盖视觉画面。

### 问题 5：安装后像临时 WebView 包，缺少专属图标

已修复：

- `android:label` 改为 `@string/app_name`。
- 添加 `ic_launcher` / `ic_launcher_round`。
- 添加 `npm run android:inspect` 检查 APK badging。

## 常用命令汇总

```bash
npm run verify
npm run release:check  # 发布前检查：当前占位 AppID/adUnitId 下应失败
npm test
npm run android:build
npm run android:inspect
adb devices -l
adb install -r android-webview/app/build/outputs/apk/debug/app-debug.apk
adb shell am force-stop com.dtalex.minigame
adb shell am start -n com.dtalex.minigame/.MainActivity
adb logcat -d -t 300 | grep -iE 'MINIGAME_WEBVIEW|Uncaught|ReferenceError|TypeError|RangeError|FATAL'
```
