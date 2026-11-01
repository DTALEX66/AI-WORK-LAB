# MINIGAME 项目清理报告（2026-07-12）

## 容量变化

- 清理前：约 4.6 GB
- 清理后：约 1.04 GB（1060.3 MiB）
- 释放：约 3.55 GB（约 77%）

## 删除的本地可再生内容

| 路径 | 清理前约占用 | 原因 |
|---|---:|---|
| `.tmp/` | 310.5 MiB | 截图、Chrome profile、审计和研究临时文件 |
| `.gradle/` | 317.1 MiB | 可再生 Gradle 缓存 |
| `android-webview/app/build/` | 159.4 MiB | 可再生 APK 与 Android 中间产物 |
| `asset-handoff-hermes-2026-07-12/` | 54.8 MiB | 已完成导入的交接副本 |
| `.tools/_downloads/` | 456 MiB | 已安装工具的下载压缩包 |
| `.tools/douyin-devtools/` | 约 2.0 GiB | 与本机正式安装版重复的便携开发者工具 |
| `.tools/android-sdk/build-tools/34.0.0/` | 137 MiB | 项目固定使用 35.0.0，旧版本无引用 |
| `android-minigame/` | 13.9 MiB | `build.js android` 可确定性重建的中间产物 |
| `android-webview/app/src/main/assets/` | 52.4 MiB | `android:prepare` 每次从源码重建的 WebView staging 目录 |

## 删除的 tracked 未接线资产

- 7 张 `assets/generated/` 旧候选图/参考屏幕。
- 2 张仅供人工总览的 spritesheet/contact sheet。
- 2 个未进入运行时的 SVG 图标文件。

同步更新了 manifest、资产 README、设计文档与库存测试，仓库中不再保留指向已删除文件的陈旧路径。

## 明确保留

- `.tools/android-sdk`（Android 35 + build-tools 35.0.0 + platform-tools）。
- `.tools/java/jdk-17`。
- `.tools/gradle/gradle-8.10.2`。
- 24 张宽屏 CCTV、24 张移动 CCTV、8 张按钮和 6 张 overlay 源资产。
- 微信、抖音的 tracked import-ready 项目；Android WebView 工程壳保留，staging 资产由 `android:prepare` 按需生成。
- `release-assets/*/screenshots/` 发布证据。
- `assets/generated/` 中仍被 `styles.css` 或皮肤运行时引用的背景、纹理和干扰层。

## 回归验证

```text
npm test: 260/260 pass
npm run skins:check: 5/5 valid
npm run content:v5:check: pass
node build.js wechat: pass
npm run douyin:build: pass
npm run douyin:check: 0 runtime blockers
npm run android:prepare: pass
```

为避免立即重新产生约 477 MiB 的 Gradle/APK缓存，本次清理后没有重新运行 `npm run android:build`；清理前提交 `c2a221b` 的 `verify:summary` 已确认 Android build 与 APK metadata 均为 OK，清理后 `android:prepare` 通过。下一次运行 Android 构建时 `.gradle/` 与 `app/build/` 会按需重建。
