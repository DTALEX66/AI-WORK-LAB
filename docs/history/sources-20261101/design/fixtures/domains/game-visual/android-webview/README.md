# Android APK WebView Adaptation

本目录是当前 H5 游戏的 Android WebView 包装工程，用于生成 debug APK，在小米手机和雷电模拟器中验收。

## 当前策略

- Android 走 WebView 包装当前 H5 版本。
- JS 使用 `build.js android` 生成单文件 IIFE，避免 Android `file://` 下 ES module 加载限制。
- H5/Android 共用 DOM 版 UI：`100dvh` 一屏控制台、CCTV 视觉监控、面板内滚动。
- Android 工程只负责壳、沉浸式全屏、WebView 设置、APK 资源与安装包元数据。

## 已验证能力

- 项目内便携工具链可构建：JDK 17、Gradle 8.10.2、Android SDK platform/build-tools 35。
- `npm run verify` 可执行完整开发验收：测试、微信 strict、Android 构建、APK 元数据检查。
- `npm run android:build` 可产出 debug APK。
- `npm run android:inspect` 可验证包名、应用名、launcher icon、minSdk、targetSdk。
- `npm run release:check` 用于发布前强校验真实 AppID / 广告位和平台 runtime blocker。
- APK 使用自定义应用名 `异常电梯控制台` 与定制 launcher icon。
- WebView console 已接入 logcat tag：`MINIGAME_WEBVIEW`。

## 完整验收

在项目根目录运行：

```bash
npm run verify
```

该命令覆盖 Node 测试、微信小游戏 strict bundle 检查、Android debug APK 构建与 APK 元数据检查。

## 适配目标

### 小米/真机竖屏

- 竖屏锁定。
- 全屏沉浸式。
- WebView text zoom 固定为 100%，避免系统字体缩放破坏 HUD。
- 使用 `100dvh` / 移动端 CSS 规则，适配高屏占比。

### 雷电模拟器

- minSdk 23，兼容常见 Android 7+ 模拟器环境。
- 竖屏运行。
- 允许本地 file asset 访问。
- 不依赖外网。

## 准备 WebView assets

在项目根目录运行：

```bash
npm run android:prepare
```

等价于：

```bash
node scripts/prepare-android-webview.mjs
```

生成：

```text
android-webview/app/src/main/assets/index.html
android-webview/app/src/main/assets/styles.css
android-webview/app/src/main/assets/game.js
```

## 构建 APK

一键构建：

```bash
npm run android:build
```

等价于：

```bash
node scripts/build-android-debug.mjs
```

产物路径：

```text
android-webview/app/build/outputs/apk/debug/app-debug.apk
```

## 检查 APK 元数据

```bash
npm run android:inspect
```

应看到：

```text
[apk-check] PASS: package is com.dtalex.minigame
[apk-check] PASS: label is 异常电梯控制台
[apk-check] PASS: launcher icon is branded ic_launcher resource
[apk-check] PASS: min sdk is 23
[apk-check] PASS: target sdk is 35
[apk-check] OK
```

## 发布前私有配置

真实微信 AppID 和激励广告位不提交到仓库。需要发布前在项目根目录复制模板：

```bash
cp release.config.example.json release.config.json
```

填入真实值后运行：

```bash
npm run release:check
```

默认占位配置下 `npm run release:check` 会故意失败；只有本地私有配置完整时才应通过。

## 导入 Android Studio

如需使用 Android Studio 调试，可导入：

```text
D:\All projects\MINIGAME\android-webview
```

也可以在该目录手动执行：

```bash
gradle --no-daemon assembleDebug
```

## 验收清单

1. 安装到小米手机或雷电模拟器。
2. 启动后应全屏竖屏显示“等待接管异常电梯”。
3. 桌面/启动器应显示应用名“异常电梯控制台”和定制图标。
4. 点击“开始接管”。
5. 主游戏界面应一屏内可玩，不需要拖动整页。
6. 监控面板应显示 CCTV/电梯轿厢/乘客热源/异常准星，文字只作为下方字幕。
7. 点击“触发异常测试”。
8. 检查：
   - 监控 HUD 出现 `SIGNAL` / `THREAT`。
   - 操作按钮可点击。
   - 日志高亮清晰。
   - 失败弹层可滚动、按钮可点。
   - 没有横向滚动、遮挡或表单感。
   - logcat 未出现 `SKIN_DATA is not defined`、`_getHiddenLog`、`RangeError`。

## 常用调试命令

一键安装并启动 debug APK：

```bash
npm run android:install
```

手动 ADB 调试命令：

```bash
adb devices -l
adb install -r android-webview/app/build/outputs/apk/debug/app-debug.apk
adb shell am force-stop com.dtalex.minigame
adb shell am start -n com.dtalex.minigame/.MainActivity
adb logcat -d -t 300 | grep -iE 'MINIGAME_WEBVIEW|Uncaught|ReferenceError|TypeError|RangeError|FATAL'
```

## 完整交接

更完整的安装、调试、发布私有配置说明见：

```text
docs/ANDROID_APK_HANDOFF.md
```
