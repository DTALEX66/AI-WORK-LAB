/**
 * build.js — 小游戏构建脚本 v2
 *
 * 将 src/ 下的 ES module 源码打包为单个 IIFE 文件，
 * 供微信/抖音小游戏使用（小游戏不支持 ESM）。
 *
 * 改进：
 *  - 修复多行 import/export 正则
 *  - 正确处理 JSON 导入顺序
 *  - 注入平台适配层
 *  - 移除运行时不需要的代码（clamp polyfill 等）
 *
 * 用法：node build.js [platform]
 *   platform: wechat (默认) | douyin
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = __dirname;

function readJsonIfExists(filePath) {
  if (!fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
}

function loadReleaseConfig() {
  const configPath = process.env.RELEASE_CONFIG_PATH
    ? path.resolve(ROOT, process.env.RELEASE_CONFIG_PATH)
    : path.join(ROOT, 'release.config.json');
  return readJsonIfExists(configPath);
}

function stableStringifyObject(value, indent = 2) {
  return JSON.stringify(value, null, indent);
}

function sortJsonValue(value) {
  if (Array.isArray(value)) return value.map(sortJsonValue);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value).sort().map(key => [key, sortJsonValue(value[key])]),
    );
  }
  return value;
}

const V5_CONTENT_FILES = [
  'anomalies',
  'endings',
  'eventChains',
  'normalShifts',
  'passengers',
  'protocols',
];

function buildV5ContentInjection() {
  const content = Object.fromEntries(V5_CONTENT_FILES.map(name => {
    const filePath = path.join(ROOT, 'src', 'content', `${name}.json`);
    return [name, sortJsonValue(JSON.parse(fs.readFileSync(filePath, 'utf-8')))];
  }));
  return `// --- V5 content (deterministic) ---\nvar __V5_CONTENT__ = ${JSON.stringify(content)};\n\n`;
}

function applyReleaseOverrides(code, modPath, target, releaseConfig) {
  // MiniGame 边界（DL-MIG）：禁止广告/IAA/发布模式语义。
  // 只保留平台 appid 私有配置注入（writePrivateProjectConfig），不注入 adUnits/releaseMode。
  return code;
}

function writePrivateProjectConfig(target, outputDir, releaseConfig) {
  const platformConfig = releaseConfig?.[target];
  if (!platformConfig?.appid) return;

  const privateConfig = {
    appid: platformConfig.appid,
    projectname: platformConfig.projectname || 'MINIGAME',
  };
  const privatePath = path.join(outputDir, 'project.private.config.json');
  fs.writeFileSync(privatePath, stableStringifyObject(privateConfig, 2), 'utf-8');
  console.log(`[build] ✅ ${target} project.private.config.json 已生成（本地私有，不提交）`);
}

const releaseConfig = loadReleaseConfig();

// ── 需要打包的模块（顺序重要） ──
// skin.json 必须在 skinManager.js 之前，因为 IIFE 顺序执行
const CORE_MODULES = [
  { path: 'src/gameConfig.js',     type: 'js' },
  { path: 'src/skins/elevator/skin.json', type: 'skin' },
  { path: 'src/skinManager.js',    type: 'js' },
  { path: 'src/rollback.js',       type: 'js' },
  { path: 'src/feedback.js',       type: 'js' },
  { path: 'src/protocolEngine.js', type: 'js' },
  { path: 'src/evidenceEngine.js', type: 'js' },
  { path: 'src/investigationTools.js', type: 'js' },
  { path: 'src/identitySystem.js', type: 'js' },
  { path: 'src/eventChainEngine.js', type: 'js' },
  { path: 'src/highRiskResolution.js', type: 'js' },
  { path: 'src/contamination.js',  type: 'js' },
  { path: 'src/debriefTimeline.js', type: 'js' },
  { path: 'src/nightInteraction.js', type: 'js' },
  { path: 'src/anomalyContent.js', type: 'js' },
  { path: 'src/visualState.js',    type: 'js' },
  { path: 'src/state.js',          type: 'js' },
  { path: 'src/incidentDecision.js', type: 'js' },
  { path: 'src/events.js',         type: 'js' },
  { path: 'src/actions.js',        type: 'js' },
  { path: 'src/uiLabels.js',       type: 'js' },
  { path: 'src/nightScheduler.js', type: 'js' },
  { path: 'src/runtimeSession.js', type: 'js' },
  { path: 'src/rewardGuard.js', type: 'js' },
  { path: 'src/firstRunGuidance.js', type: 'js' },
];

const DOM_ENTRY_MODULES = [
  ...CORE_MODULES,
  { path: 'src/analytics.js',      type: 'js' },
  { path: 'src/archive.js',        type: 'js' },
  { path: 'src/audio.js',          type: 'js' },
  { path: 'platform/platform.js',   type: 'js' },
  { path: 'src/game.js',           type: 'js' },
];

const MINI_ENTRY_MODULES = [
  ...CORE_MODULES.filter(module => module.path !== 'src/uiLabels.js'),
  { path: 'platform/canvasLabels.js', type: 'js' },
  { path: 'platform/canvasAssets.js', type: 'js' },
  { path: 'platform/miniGameClock.js', type: 'js' },
  { path: 'platform/cctvMotion.js', type: 'js' },
  { path: 'platform/miniGameAudio.js', type: 'js' },
  { path: 'platform/douyinIntegration.js', type: 'js' },
  { path: 'platform/canvasRenderer.js', type: 'js' },
  { path: 'platform/miniGameRuntime.js', type: 'js' },
];

/**
 * 移除 ESM import/export 语句（支持单行和多行）
 */
function stripESM(code) {
  // 移除 import ... from '...'，兼容 JSON import attributes: with { type: 'json' }
  code = code.replace(/^import\s+.+\s+from\s+['"].+['"](?:\s+with\s+\{[^}]+\})?;?\s*$/gm, '');
  // 移除多行 import { \n ... \n } from '...'
  code = code.replace(/^import\s*\{[\s\S]*?\}\s*from\s*['"].+['"];?\s*/gm, '');
  // 移除顶级 import '...'
  code = code.replace(/^import\s+['"].+['"];?\s*$/gm, '');
  // 移除 export default
  code = code.replace(/^export\s+default\s+/gm, '');
  // 移除 export function / const / let / var / class
  code = code.replace(/^export\s+(function|const|let|var|class)\s+/gm, '$1 ');
  // 移除单行 export { ... }
  code = code.replace(/^export\s*\{[^}]+\};?\s*$/gm, '');
  // 移除多行 export { \n ... \n }
  code = code.replace(/^export\s*\{[\s\S]*?\};?\s*/gm, '');
  return code;
}

function collectModuleExports(code) {
  const exports = [];
  const seen = new Set();
  const add = (local, exported = local) => {
    const key = `${local}:${exported}`;
    if (!seen.has(key)) {
      seen.add(key);
      exports.push({ local, exported });
    }
  };

  for (const match of code.matchAll(/^export\s+(?:async\s+)?(?:function|const|let|var|class)\s+([A-Za-z_$][\w$]*)/gm)) {
    add(match[1]);
  }
  for (const match of code.matchAll(/^export\s*\{([^}]+)\};?\s*$/gm)) {
    for (const specifier of match[1].split(',')) {
      const [local, exported = local] = specifier.trim().split(/\s+as\s+/);
      if (local) add(local, exported);
    }
  }
  const defaultMatch = code.match(/^export\s+default\s+([A-Za-z_$][\w$]*)\s*;?\s*$/m);
  if (defaultMatch) add(defaultMatch[1]);
  return exports;
}

function isolateModule(code, modPath) {
  const moduleExports = collectModuleExports(code);
  const stripped = stripESM(code);
  const safeModuleId = modPath.replace(/[^A-Za-z0-9_$]/g, '_');
  const exportBag = `__exports_${safeModuleId}`;
  const captures = moduleExports
    .map(({ local, exported }) => `${exportBag}[${JSON.stringify(exported)}] = ${local};`)
    .join('\n');
  const lifts = moduleExports
    .map(({ exported }) => `var ${exported} = ${exportBag}[${JSON.stringify(exported)}];`)
    .join('\n');

  return `var ${exportBag} = {};\n{\n${stripped}\n${captures}\n}\n${lifts}`;
}

function bundle(target) {
  const modules = target === 'wechat' || target === 'douyin'
    ? MINI_ENTRY_MODULES
    : DOM_ENTRY_MODULES;
  const targetLabel = target === 'wechat' ? '微信' : target === 'douyin' ? '抖音' : 'Android WebView';
  const top = `/**
 * MINIGAME - ${targetLabel} 小游戏构建
 * 构建标记: deterministic
 * 请勿手动修改此文件
 */
(function() {
'use strict';

`;

  let body = buildV5ContentInjection();
  let bottom = '';

  for (const mod of modules) {
    const fullPath = path.join(ROOT, mod.path);
    if (!fs.existsSync(fullPath)) {
      console.warn(`[build] 警告: ${mod.path} 不存在，跳过`);
      continue;
    }

    const raw = fs.readFileSync(fullPath, 'utf-8');

    if (mod.type === 'skin') {
      // 将 JSON 注入为全局变量；小游戏发布包移除浏览器专用调试字段。
      const skinData = JSON.parse(raw);
      if ((target === 'wechat' || target === 'douyin') && skinData.canvasLabels) {
        delete skinData.canvasLabels.forceAnomaly;
      }
      const min = JSON.stringify(skinData); // 压缩+验证
      body += `// --- ${mod.path} ---\nvar __SKIN_DATA__ = ${min};\n\n`;
    } else {
      let code = applyReleaseOverrides(raw, mod.path, target, releaseConfig);
      // 替换 skinManager 中的 import 为 __SKIN_DATA__
      if (mod.path === 'src/skinManager.js') {
        code = code.replace(/\bSKIN_DATA\b/g, '__SKIN_DATA__');
      }
      if (mod.path === 'src/events.js') {
        code = code.replace(
          /\n\s*\/\/ 向后兼容导出\s*\nexport\s+function getHiddenLog\(anomalyId\)\s*\{\s*return _getHiddenLog\(anomalyId\);\s*\}\s*\n/g,
          '\n',
        );
        code = code.replace(
          /(import\s+\{\s*getAnomalies,\s*getHiddenLog\s+as\s+_getHiddenLog,\s*t\s*\}\s+from\s+['"]\.\/skinManager\.js['"];?)/,
          '$1\nconst _getHiddenLog = getHiddenLog;',
        );
        code = code.replace(/\b_getHiddenLog\b/g, 'skinHiddenLogLookup');
      }
      // 移除 skinManager 中死代码（buildHiddenLogsMap 的 require mock）
      code = code.replace(/function buildHiddenLogsMap[\s\S]*?\n\}/g, 'function buildHiddenLogsMap() { return {}; }');
      body += `// --- ${mod.path} ---\n${isolateModule(code, mod.path)}\n\n`;
    }
  }

  // 注入平台启动代码
  if (target === 'wechat') {
    bottom = `
// ── 平台入口 ──
startMiniGame();
})();
`;
  } else if (target === 'douyin') {
    bottom = `
// ── 平台入口 ──
startMiniGame();
})();
`;
  } else {
    bottom = `
// ── 启动 ──
console.log('[MINIGAME] Running on', '${target}');
})();
`;
  }

  return top + body + bottom;
}

// ── 写入 ──
const target = process.argv[2] || 'wechat';
const outputDir = path.join(ROOT, `${target}-minigame`);
fs.mkdirSync(outputDir, { recursive: true });
const legacyOutputDir = path.join(outputDir, '电梯异常');
if (fs.existsSync(legacyOutputDir)) {
  fs.rmSync(legacyOutputDir, { recursive: true, force: true });
  console.log(`[build] ✅ 已清理旧版输出目录: ${legacyOutputDir}`);
}

const bundled = bundle(target);
const outPath = path.join(outputDir, 'game.js');
fs.writeFileSync(outPath, bundled, 'utf-8');
writePrivateProjectConfig(target, outputDir, releaseConfig);

// 视觉资产与音频资产已随 minigame 视觉资产清理一并移除；
// 小游戏构建仅输出纯代码 bundle，不再同步 visual/ 或 audio/ 资产目录。

console.log(`[build] ✅ ${target} 构建完成`);
console.log(`[build]   输出: ${outPath}`);
console.log(`[build]   大小: ${(bundled.length / 1024).toFixed(1)} KB`);

// ── 创建项目配置；存在 ignored release.config.json 时让开发工具直接读取真实 AppID ──
const projectConfig = target === 'douyin'
  ? {
      description: 'MINIGAME - 异常电梯控制台（抖音小游戏）',
      miniprogramRoot: './',
      setting: {
        urlCheck: true,
        es6: true,
        minified: true,
      },
      compileType: 'game',
      libVersion: 'latest',
      appid: releaseConfig?.douyin?.appid || 'touristappid',
      projectname: releaseConfig?.douyin?.projectname || '异常电梯控制台',
      condition: {},
    }
  : {
      description: 'MINIGAME - 异常系统模拟类小游戏',
      setting: {
        urlCheck: true,
        es6: true,
        postcss: true,
        minified: true,
        enhance: true,
        condition: false,
      },
      compileType: 'game',
      libVersion: 'latest',
      appid: releaseConfig?.wechat?.appid || 'touristappid',
      projectname: releaseConfig?.wechat?.projectname || 'MINIGAME',
      condition: {},
    };
fs.writeFileSync(
  path.join(outputDir, 'project.config.json'),
  JSON.stringify(projectConfig, null, 2),
  'utf-8',
);
console.log(`[build] ✅ ${target} project.config.json 已生成`);

const gameConfig = {
  deviceOrientation: 'portrait',
  showStatusBar: false,
  networkTimeout: { request: 5000, connectSocket: 5000 },
};
fs.writeFileSync(
  path.join(outputDir, 'game.json'),
  JSON.stringify(gameConfig, null, 2),
  'utf-8',
);
console.log(`[build] ✅ ${target} game.json 已生成`);
