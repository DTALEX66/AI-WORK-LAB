/**
 * gameConfig.js — MINIGAME 平衡参数配置（单一配置源）
 *
 * v2.0 平衡调优：
 * - 更平滑的难度曲线
 * - 操作策略深度加深
 * - 新手友好但高手有挑战
 *
 * 用法：
 *   import CONFIG from './gameConfig.js';
 *   CONFIG.tick.powerDrainMoving  // 0.5
 */

const CONFIG = {
  /* ── 初始状态 ── */
  initial: {
    floor: 1,
    door: 'closed',
    moving: false,
    direction: 'idle',
    power: 100,
    stability: 100,
    anomalyLevel: 0,
    passengers: 0,
    gameOver: false,
    duration: 60,          // 值守倒计时（秒）
  },

  /* ── 每 Tick（1 秒）消耗 ── */
  tick: {
    powerDrainMoving: 0.5,    // 移动中每秒电源消耗（↓0.7）
    powerDrainIdle: 0.15,     // 待机每秒电源消耗（↓0.18）
    stabilityDrainMoving: 0.2, // 移动中每秒稳定度消耗（↓0.25）
  },

  /* ── 操作消耗/效果 ── */
  actions: {
    moveUp: {
      powerCost: 5,           // ↓6
      stabilityCost: 1.5,     // ↓2
    },
    moveDown: {
      powerCost: 5,           // ↓6
      stabilityCost: 1.5,     // ↓2
    },
    emergencyStop: {
      stabilityCost: 4,       // ↓6
      stabilityCostOnFailure: 12, // ↓16 急停失效时的额外惩罚
    },
    restartSystem: {
      anomalyLevelReduce: 2,
      stabilityRestore: 20,   // ↑15 更值得用
      powerCost: 8,           // ↓10
    },
  },

  /* ── 失败条件 ── */
  failure: {
    powerMin: 0,
    stabilityMin: 0,
    anomalyLevelMax: 6,
    passengersMin: 0,
  },

  /* ── 世界边界 ── */
  bounds: {
    maxFloor: 30,
  },

  /* ── 异常系统 ── */
  anomaly: {
    firstTriggerAt: 8,          // 首局 10 秒内抛出异常，尽快进入找异常循环
    firstMaxSeverity: 2,        // 首个异常只做教学压力，不直接抽高危事件
    cooldownMin: 8,             // 双按钮循环：每局约 6–7 个异常
    cooldownMax: 11,            // 异常间插入正常班次，保持高密度但可观察
    pressureDivisor: 2,         // pickNextAnomaly 压力算法分母

    // 难度递增：每 elapsedSeconds 的异常效果乘数
    // formula: Math.pow(difficultyScale, elapsedSeconds / difficultyInterval)
    difficultyScale: 1.06,      // 每 10 秒异常效果变为 1.06x
    difficultyInterval: 10,     // 间隔秒数
  },

  /* ── 复活（回滚快照机制，无广告） ── */
  revive: {
    rollbackWindow: 30,          // 回滚到多少秒前的快照
    snapshotInterval: 10,        // 每 N 秒存一次快照
    maxSnapshots: 12,            // 最多保留快照数
  },

  /* ── 日志 ── */
  logs: {
    maxLines: 80,
    displayLines: 18,
  },

  /* ── 隐藏日志（解码） ── */
  hiddenLogs: {
    maxUnlockedPerRun: 5,
  },

  /* ── 假结局 ── */
  fakeEnding: {
    consecutiveFailuresThreshold: 5,
    cooldownFailures: 3,
  },



};

export default CONFIG;
