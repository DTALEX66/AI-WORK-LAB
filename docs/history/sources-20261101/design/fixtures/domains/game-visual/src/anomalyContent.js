/**
 * anomalyContent.js — 异常内容模式定义与结构化数据
 *
 * 为每个异常定义正式的 screenData / panelData / primaryConflict 三元组，
 * 确保所有判断基于具体可观察线索，而非标题/颜色/答案高亮。
 *
 * 设计原则（#6、#7）：
 * - 静音和色盲状态下仍可判断（线索为文字/数据矛盾，不依赖声音或颜色）
 * - 每项异常必须具备可观察、可解释、可复盘的具体线索
 * - screenData 和 panelData 同时可供生成 CCTV 素材时的来源字段
 */

// ─── 类型文档 ──────────────────────────────────────────────
/**
 * @typedef {Object} AnomalyContent
 * @property {string}   id                  — 异常 ID，与 skin.json 与 events.js 一致
 * @property {string}   title               — 短标题
 * @property {number}   severity            — 1=轻度 2=中度 3=重度
 * @property {1|2|3}    difficulty          — 玩家判断难度 1=明显矛盾 2=需核对 3=需复盘
 * @property {'release'|'lockdown'} correctDecision — 正确玩家操作
 *
 * @property {Object}   screenData          — CCTV 画面呈现的数据
 * @property {number}   screenData.floor    — 画面中显示的楼层号
 * @property {number}   screenData.passengers — 画面中可见人数
 * @property {'open'|'closed'} screenData.door — 画面中门状态
 * @property {'idle'|'up'|'down'} screenData.direction — 画面中电梯方向
 *
 * @property {Object}   panelData           — 控制台面板显示的数据
 * @property {number}   panelData.floor
 * @property {number}   panelData.passengers
 * @property {'open'|'closed'} panelData.door
 * @property {'idle'|'up'|'down'} panelData.direction
 *
 * @property {string}   primaryConflict     — 关键矛盾的中文描述（局后复盘用）
 * @property {string}   explanation         — 异常原因的中文说明（档案库用）
 * @property {string}   visualState         — 对应的 CCTV 状态 ID
 * @property {string}   audioCue            — 异常触发时的音频 cue 名称
 * @property {string}   resolutionAction    — 系统自动处置动作 ID
 * @property {string}   monitorTemplate     — 皮肤 monitor 文案 key 或模板
 * @property {number}   stabilityPenalty    — 稳定度基准惩罚（已乘难度系数前）
 * @property {number}   powerPenalty        — 电源基准惩罚
 *
 * @property {Object}   [normalVariant]     — 对应的正常变体（用于随机正常班次）
 * @property {number}   normalVariant.floor
 * @property {number}   normalVariant.passengers
 * @property {'open'|'closed'} normalVariant.door
 * @property {'idle'|'up'|'down'} normalVariant.direction
 */

// ─── 类别说明 ──────────────────────────────────────────────
// 单项数据矛盾：screenData 与 panelData 仅一个字段不同
// 延迟/状态冲突：screenData 显示的是上一帧或错误状态
// 视觉复合异常：多个字段同时矛盾，或存在逻辑矛盾

/** @type {AnomalyContent[]} */
export const ANOMALY_CONTENTS = [
  // ══════════════════════════════════════════════════════════
  // 4 个单项数据矛盾
  // ══════════════════════════════════════════════════════════
  {
    id: 'phantom_floor',
    title: '不存在的楼层',
    severity: 2,
    difficulty: 1,
    correctDecision: 'lockdown',

    screenData: { floor: 4, passengers: 1, door: 'closed', direction: 'idle' },
    panelData:  { floor: 2,  passengers: 1, door: 'closed', direction: 'idle' },

    primaryConflict: '画面楼层比控制台高 2 层（画面层 4，控制台层 2）',
    explanation: '电梯在建筑图纸不存在的夹层停靠。该夹层位于正常楼层之间，施工记录已丢失，但控制面板仍能收到来自该层的信号。',
    visualState: '16_wrong_floor',
    audioCue: 'anomaly',
    resolutionAction: 'restartSystem',
    monitorTemplate: '监控：楼层读数跳到 {normalFloorPlus2} 层。该楼层在建筑图纸中不存在。',
    stabilityPenalty: -10,
    powerPenalty: 0,

    normalVariant: { floor: 2, passengers: 1, door: 'closed', direction: 'idle' },
  },

  {
    id: 'negative_floor',
    title: '楼层显示为负数',
    severity: 2,
    difficulty: 1,
    correctDecision: 'lockdown',

    screenData: { floor: -1, passengers: 1, door: 'closed', direction: 'down' },
    panelData:  { floor: 5,  passengers: 1, door: 'closed', direction: 'down' },

    primaryConflict: '画面显示 -1 层，控制台显示 5 层',
    explanation: '电梯进入建筑图纸未标注的地下结构。实际存在 B3-B4 层，但按钮在出厂时已被移除，线路仍然通电。',
    visualState: '16_wrong_floor',
    audioCue: 'anomaly',
    resolutionAction: 'restartSystem',
    monitorTemplate: '监控：楼层显示 -1。摄像头画面出现地下走廊。',
    stabilityPenalty: -10,
    powerPenalty: 0,

    normalVariant: { floor: 5, passengers: 1, door: 'closed', direction: 'down' },
  },

  {
    id: 'weight_mismatch',
    title: '载重数据异常',
    severity: 1,
    difficulty: 2,
    correctDecision: 'lockdown',

    screenData: { floor: 1, passengers: 1, door: 'closed', direction: 'idle' },
    panelData:  { floor: 1, passengers: 0, door: 'closed', direction: 'idle' },

    primaryConflict: '画面有 1 人，控制台乘客计数为 0',
    explanation: '红外传感器在轿厢内检测到热源信号，但载重传感器读数为零。热源信号经比对与员工体温档案不匹配。',
    visualState: '14_shadow_inside',
    audioCue: 'anomaly',
    resolutionAction: 'inspectLog',
    monitorTemplate: '监控：载重传感器读数 — 0kg。轿厢内有 1 名乘客。读数矛盾。',
    stabilityPenalty: -7,
    powerPenalty: 0,

    normalVariant: { floor: 1, passengers: 1, door: 'closed', direction: 'idle' },
  },

  {
    id: 'zero_passenger_shadow',
    title: '门外有人但乘客数为 0',
    severity: 2,
    difficulty: 2,
    correctDecision: 'lockdown',

    screenData: { floor: 3, passengers: 1, door: 'open', direction: 'idle' },
    panelData:  { floor: 3, passengers: 0, door: 'open', direction: 'idle' },

    primaryConflict: '画面显示 1 人在外等候，控制台乘客计数为 0',
    explanation: '红外传感器在非营业时段多次检测到热源信号，但乘客计数器持续归零。传感器无硬件故障。',
    visualState: '15_anomaly_wandering',
    audioCue: 'anomaly',
    resolutionAction: 'inspectLog',
    monitorTemplate: '监控：门外站着一个人，但乘客计数器显示 0。',
    stabilityPenalty: -12,
    powerPenalty: 0,

    normalVariant: { floor: 3, passengers: 1, door: 'open', direction: 'idle' },
  },

  // ══════════════════════════════════════════════════════════
  // 4 个延迟/状态冲突
  // ══════════════════════════════════════════════════════════
  {
    id: 'camera_delay',
    title: '监控延迟',
    severity: 1,
    difficulty: 2,
    correctDecision: 'lockdown',

    screenData: { floor: 5, passengers: 2, door: 'closed', direction: 'up' },
    panelData:  { floor: 7, passengers: 2, door: 'closed', direction: 'up' },

    primaryConflict: 'CCTV 楼层停留在 5 层，控制台已到 7 层',
    explanation: '摄像头#03 与#07 存在持续信号延迟。延迟与第 13 层信号干扰有关，不建议在该层停靠。',
    visualState: '11_camera_glitch',
    audioCue: 'anomaly',
    resolutionAction: 'inspectLog',
    monitorTemplate: '监控：画面延迟 3 秒。乘客动作与控制台记录不同步。',
    stabilityPenalty: -6,
    powerPenalty: 0,

    normalVariant: { floor: 7, passengers: 2, door: 'closed', direction: 'up' },
  },

  {
    id: 'door_refuse',
    title: '电梯门拒绝关闭',
    severity: 2,
    difficulty: 2,
    correctDecision: 'lockdown',

    screenData: { floor: 4, passengers: 1, door: 'open', direction: 'idle' },
    panelData:  { floor: 4, passengers: 1, door: 'closed', direction: 'idle' },

    primaryConflict: '画面显示门开着，控制台显示门已关闭',
    explanation: '门控模块在连续 3 次异常重启后进入保护模式。模块检测到外部干扰信号，拒绝执行关门指令以保护乘员安全。',
    visualState: '09_door_jammed',
    audioCue: 'anomaly',
    resolutionAction: 'closeDoor',
    monitorTemplate: '监控：关门按钮已按下，门在合拢前自动弹开。异常状态持续。',
    stabilityPenalty: -10,
    powerPenalty: 0,

    normalVariant: { floor: 4, passengers: 1, door: 'closed', direction: 'idle' },
  },

  {
    id: 'log_echo',
    title: '系统日志重复字符',
    severity: 1,
    difficulty: 2,
    correctDecision: 'lockdown',

    screenData: { floor: 2, passengers: 1, door: 'closed', direction: 'idle' },
    panelData:  { floor: 2, passengers: 1, door: 'closed', direction: 'idle' },

    primaryConflict: '画面和控制台数据一致，但日志系统输出异常（画面三要素一致时仍需判断日志线索）',
    explanation: '系统日志缓冲区检测到重复写入操作。重复内容「不要开门」的写入时间戳早于当前值班员登录时间，表明前一值班员的退出状态异常。',
    visualState: '17_loop_corridor',
    audioCue: 'anomaly',
    resolutionAction: 'inspectLog',
    monitorTemplate: '监控：系统日志开始重复输出"不要开门"。',
    stabilityPenalty: -5,
    powerPenalty: 0,

    normalVariant: { floor: 2, passengers: 1, door: 'closed', direction: 'idle' },
  },

  {
    id: 'auto_button',
    title: '按钮自动亮起',
    severity: 2,
    difficulty: 3,
    correctDecision: 'lockdown',

    screenData: { floor: 6, passengers: 0, door: 'closed', direction: 'idle' },
    panelData:  { floor: 6, passengers: 0, door: 'closed', direction: 'idle' },

    primaryConflict: '画面三要素一致，但控制台有非授权楼层请求（B2 和 9 层按钮自动亮起）',
    explanation: '自动按钮信号来源追溯至 5 号服务器（已于 2022 年停用）。该服务器的最后一条记录为「控制权移交程序未完成」。',
    visualState: '12_scan_active',
    audioCue: 'anomaly',
    resolutionAction: 'restartSystem',
    monitorTemplate: '监控：没有乘客触碰按钮，B2 与 9 层按钮自动亮起。',
    stabilityPenalty: 0,
    powerPenalty: -8,

    normalVariant: { floor: 6, passengers: 0, door: 'closed', direction: 'idle' },
  },

  // ══════════════════════════════════════════════════════════
  // 4 个视觉复合异常
  // ══════════════════════════════════════════════════════════
  {
    id: 'stop_failure',
    title: '急停按钮失效',
    severity: 3,
    difficulty: 3,
    correctDecision: 'lockdown',

    screenData: { floor: 8, passengers: 2, door: 'closed', direction: 'down' },
    panelData:  { floor: 8, passengers: 2, door: 'closed', direction: 'down' },

    primaryConflict: '画面三要素一致，但急停指示灯熄灭且控制台拒绝确认安全回路（复合硬件异常）',
    explanation: '急停回路#2 在定期检查中被标记为「不可用」。签署人签名无法识别，签署时间为 3 年前，没有后续维修记录。',
    visualState: '08_emergency_stop',
    audioCue: 'anomaly',
    resolutionAction: 'restartSystem',
    monitorTemplate: '监控：急停按钮指示灯熄灭，控制台拒绝确认安全回路。',
    stabilityPenalty: -15,
    powerPenalty: 0,

    normalVariant: { floor: 8, passengers: 2, door: 'closed', direction: 'down' },
  },

  {
    id: 'power_drain',
    title: '电源异常下降',
    severity: 2,
    difficulty: 2,
    correctDecision: 'lockdown',

    screenData: { floor: 7, passengers: 1, door: 'closed', direction: 'idle' },
    panelData:  { floor: 7, passengers: 1, door: 'closed', direction: 'idle' },

    primaryConflict: '画面三要素一致，但电源持续下降（非正常消耗速率，需观察电源条趋势）',
    explanation: '备用电源在无负载状态下持续放电。有一条非授权线路从备用电源柜分接至未知设备，线路标签为「不要切断」。',
    visualState: '06_power_low',
    audioCue: 'anomaly',
    resolutionAction: 'restartSystem',
    monitorTemplate: '监控：备用电源自动接管，但电量仍在下降。',
    stabilityPenalty: 0,
    powerPenalty: -22,

    normalVariant: { floor: 7, passengers: 1, door: 'closed', direction: 'idle' },
  },

  {
    id: 'floor_jump',
    title: '楼层编号跳跃',
    severity: 2,
    difficulty: 2,
    correctDecision: 'lockdown',

    screenData: { floor: 9, passengers: 1, door: 'closed', direction: 'up' },
    panelData:  { floor: 5, passengers: 1, door: 'closed', direction: 'up' },

    primaryConflict: 'CCTV 直接显示 9 层，控制台仍在 5 层（非连续移动，帧丢失）',
    explanation: 'GPS 楼层定位模块在校准前后记录的楼层编号不一致。系统自动修正失败，参考信号源来自非标设备。',
    visualState: '16_wrong_floor',
    audioCue: 'anomaly',
    resolutionAction: 'inspectLog',
    monitorTemplate: '监控：电梯从 5 层直接移动到 9 层。摄像头画面缺失 4 帧。',
    stabilityPenalty: -12,
    powerPenalty: -10,

    normalVariant: { floor: 5, passengers: 1, door: 'closed', direction: 'up' },
  },

  {
    id: 'emergency_lights',
    title: '应急灯异常启动',
    severity: 3,
    difficulty: 3,
    correctDecision: 'lockdown',

    screenData: { floor: 10, passengers: 2, door: 'closed', direction: 'idle' },
    panelData:  { floor: 10, passengers: 2, door: 'closed', direction: 'idle' },

    primaryConflict: '画面三要素一致，但应急灯突然亮起且备用电源加速消耗（需识别异常氛围与电源趋势的复合矛盾）',
    explanation: '应急照明系统在无触发信号的情况下自行启动。供电线路检测到寄生回路，终端设备编号无法匹配任何已知设备清单。',
    visualState: '07_power_outage',
    audioCue: 'anomaly',
    resolutionAction: 'restartSystem',
    monitorTemplate: '监控：轿厢应急灯突然亮起。备用电源消耗加速。',
    stabilityPenalty: -14,
    powerPenalty: -20,

    normalVariant: { floor: 10, passengers: 2, door: 'closed', direction: 'idle' },
  },
];

// ─── 辅助函数 ──────────────────────────────────────────────

/** 按 ID 查找异常内容 */
export function findAnomalyContent(id) {
  return ANOMALY_CONTENTS.find(a => a.id === id) || null;
}

/** 获取所有异常内容 */
export function getAllAnomalyContents() {
  return ANOMALY_CONTENTS;
}

/** 判断 screenData 与 panelData 是否一致（正常班次条件） */
export function isDataConsistent(content) {
  return (
    content.screenData.floor === content.panelData.floor &&
    content.screenData.passengers === content.panelData.passengers &&
    content.screenData.door === content.panelData.door &&
    content.screenData.direction === content.panelData.direction
  );
}

/** 获取 primaryConflict 列表 */
export function getConflictFields(content) {
  const conflicts = [];
  if (content.screenData.floor !== content.panelData.floor) conflicts.push('floor');
  if (content.screenData.passengers !== content.panelData.passengers) conflicts.push('passengers');
  if (content.screenData.door !== content.panelData.door) conflicts.push('door');
  if (content.screenData.direction !== content.panelData.direction) conflicts.push('direction');
  return conflicts;
}

// ─── 10+ 正常班次变体 ──────────────────────────────────
//
// 这些变体用于生成与异常画面相似但数据一致的正常巡检，
// 避免玩家形成"画面变化 = 异常"的条件反射。
//
// 每个变体：screenData === panelData（三要素一致）

/**
 * @typedef {Object} NormalVariant
 * @property {number} floor
 * @property {number} passengers
 * @property {'open'|'closed'} door
 * @property {'idle'|'up'|'down'} direction
 * @property {string} scenario   — 场景中文描述
 * @property {string} visualState — CCTV 状态 ID
 */

/** @type {NormalVariant[]} */
export const NORMAL_VARIANTS = [
  // 空轿厢静止
  { floor: 1,  passengers: 0, door: 'closed', direction: 'idle', scenario: '首层待机，轿厢空载', visualState: '00_idle_closed' },

  // 单乘客正常移动
  { floor: 3,  passengers: 1, door: 'closed', direction: 'up',   scenario: '单客上行至 3 层', visualState: '04_moving_up' },
  { floor: 6,  passengers: 1, door: 'closed', direction: 'down', scenario: '单客下行至 6 层', visualState: '05_moving_down' },

  // 多乘客接客
  { floor: 2,  passengers: 2, door: 'open',  direction: 'idle', scenario: '2 层开门接客，2 人在外等候', visualState: '01_door_open' },
  { floor: 5,  passengers: 3, door: 'closed', direction: 'up',   scenario: '3 人上行至 5 层', visualState: '04_moving_up' },

  // 中等楼层
  { floor: 8,  passengers: 0, door: 'closed', direction: 'idle', scenario: '8 层待机，空载', visualState: '00_idle_closed' },
  { floor: 10, passengers: 1, door: 'closed', direction: 'down', scenario: '10 层下行，单客回家', visualState: '05_moving_down' },
  { floor: 4,  passengers: 2, door: 'open',  direction: 'idle', scenario: '4 层开门，2 人出梯', visualState: '02_door_opening' },

  // 接近异常的楼层但数据一致（防止模式识别）
  { floor: 13, passengers: 0, door: 'closed', direction: 'idle', scenario: '13 层待机（已开门），空载——普通停靠并非异常', visualState: '01_door_open' },
  { floor: -1, passengers: 0, door: 'closed', direction: 'idle', scenario: '-1 层（地下停车场标准层）待机', visualState: '00_idle_closed' },

  // 方向变化
  { floor: 7,  passengers: 1, door: 'closed', direction: 'up',   scenario: '单客上行前往 7 层', visualState: '04_moving_up' },
  { floor: 9,  passengers: 2, door: 'closed', direction: 'down', scenario: '2 人从 9 层下行', visualState: '05_moving_down' },
];

/** 获取随机正常变体 */
export function pickNormalVariant(random = Math.random) {
  return NORMAL_VARIANTS[Math.floor(random() * NORMAL_VARIANTS.length)];
}

// ─── CCTV 状态映射 ──────────────────────────────────
//
// 完整 CCTV 资产状态列表（按 ID 排序以匹配 asset manifest）
// 00_idle_closed    01_door_open     02_door_opening  03_door_closing
// 04_moving_up      05_moving_down   06_power_low     07_power_outage
// 08_emergency_stop 09_door_jammed   10_signal_lost   11_camera_glitch
// 12_scan_active    13_entity_near   14_shadow_inside 15_anomaly_wandering
// 16_wrong_floor    17_loop_corridor 18_corridor_dark 19_stabilized
// 20_threat_high    21_containment   22_system_reboot 23_cooldown_safe

/** 按 anomaly ID 获取 CCTV 状态 */
export function getAnomalyCctvState(anomalyId) {
  return ANOMALY_CONTENTS.find(a => a.id === anomalyId)?.visualState || null;
}

/** 按 CCTV 状态 ID 获取该状态对应的所有异常 ID */
export function getAnomaliesByCctvState(cctvState) {
  return ANOMALY_CONTENTS
    .filter(a => a.visualState === cctvState)
    .map(a => a.id);
}

/** 获取所有正常 CCTV 状态列表（无异常时可见） */
export function getNormalCctvStates() {
  return [
    '00_idle_closed', '01_door_open', '02_door_opening', '03_door_closing',
    '04_moving_up', '05_moving_down', '19_stabilized', '23_cooldown_safe',
  ];
}

/** 获取所有异常 CCTV 状态列表 */
export function getAnomalyCctvStates() {
  const states = new Set(ANOMALY_CONTENTS.map(a => a.visualState));
  return [...states];
}
