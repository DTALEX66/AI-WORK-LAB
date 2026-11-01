# Game001 V5 Phase A — 夜班协议数据地基

## 范围

本阶段只建立共享逻辑和数据契约，不改 Canvas V4 玩家界面，不引入第二游戏、新皮肤或旧式多按钮控制台。

## 已建立的共享模块

- `src/protocolEngine.js`：每局生成 2—3 条协议，并保证至少一条可作用于本局班次；协议判断输出可靠查证路径。
- `src/evidenceEngine.js`：统一比较楼层、人数、门状态；判断前保持中性，不通过颜色或标题泄露答案；支持静音可判断性检查。
- `src/contamination.js`：污染度 0—100、四阶段、因果历史和不泄题的视觉/可靠路径派生。
- `src/state.js`：初始状态接入结构化污染度。

## 内容容器

- `src/content/protocols.json`：首批 6 条协议地基。
- `src/content/normalShifts.json`：阶段 B 填充。
- `src/content/anomalies.json`：阶段 B 填充。
- `src/content/eventChains.json`：阶段 B 填充。
- `src/content/endings.json`：阶段 D 填充。

空容器是有意的阶段边界，不表示对应内容已经完成。

## Schema

`schemas/` 下包含 protocol、normal shift、anomaly content、event chain、ending 五类 JSON Schema。异常 schema 强制要求：画面数据、主控数据、明确冲突、决定、解释、处置、工具、协议标签、污染影响和静音替代证据。

## 验证

```bash
node --test tests/protocolEngine.test.js tests/evidenceEngine.test.js tests/contamination.test.js tests/contentSchemasV5.test.js
npm run content:v5:check
npm test
npm run skins:check
npm run verify:summary
```
