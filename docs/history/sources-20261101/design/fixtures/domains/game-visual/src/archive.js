// archive.js — cross-session anomaly archive (localStorage-backed).
// Survives page reloads and browser restarts on the same device.

const STORAGE_KEY = 'minigame_archive_v1';

const DEFAULT_SKIN_PROGRESS = {
  sessionsPlayed: 0,
  totalAnomaliesTriggered: 0,
  totalLogsUnlocked: 0,
  encounteredAnomalies: {},   // id → count
  unlockedLogs: {},           // log id → true
  highestSeverity: 0,
};

const DEFAULT = {
  sessionsPlayed: 0,
  totalAnomaliesTriggered: 0,
  totalLogsUnlocked: 0,
  encounteredAnomalies: {},   // id → count
  unlockedLogs: {},           // log id → true
  highestSeverity: 0,
  skins: {},                  // skinId → DEFAULT_SKIN_PROGRESS
};

function cloneDefaultSkinProgress() {
  return structuredClone(DEFAULT_SKIN_PROGRESS);
}

function normalizeArchive(raw) {
  const archive = { ...structuredClone(DEFAULT), ...(raw || {}) };
  archive.encounteredAnomalies ||= {};
  archive.unlockedLogs ||= {};
  archive.skins ||= {};
  for (const [skinId, progress] of Object.entries(archive.skins)) {
    archive.skins[skinId] = {
      ...cloneDefaultSkinProgress(),
      ...(progress || {}),
      encounteredAnomalies: { ...(progress?.encounteredAnomalies || {}) },
      unlockedLogs: { ...(progress?.unlockedLogs || {}) },
    };
  }
  return archive;
}

function getOrCreateSkinProgress(archive, skinId) {
  if (!skinId) return null;
  if (!archive.skins[skinId]) archive.skins[skinId] = cloneDefaultSkinProgress();
  return archive.skins[skinId];
}

/** @returns {typeof DEFAULT} */
export function loadArchive() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return structuredClone(DEFAULT);
    return normalizeArchive(JSON.parse(raw));
  } catch {
    return structuredClone(DEFAULT);
  }
}

export function saveArchive(archive) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(archive));
  } catch {
    // quota exceeded or private browsing — silently skip
  }
}

/**
 * Merge one session's results into the archive.
 * @param {object} sessionSummary
 * @param {string} [sessionSummary.skinId]
 * @param {number} sessionSummary.anomaliesTriggeredTotal
 * @param {number} sessionSummary.maxAnomalySeverity
 * @param {string[]} sessionSummary.anomalyIds — all anomaly IDs triggered this session
 * @param {string[]} sessionSummary.unlockedLogIds — hidden log IDs unlocked this session
 */
export function commitSessionToArchive(sessionSummary) {
  const archive = loadArchive();
  const skinProgress = getOrCreateSkinProgress(archive, sessionSummary.skinId);
  const unlockedLogIds = sessionSummary.unlockedLogIds || [];

  archive.sessionsPlayed += 1;
  archive.totalAnomaliesTriggered += sessionSummary.anomaliesTriggeredTotal || 0;
  archive.totalLogsUnlocked += unlockedLogIds.length;
  archive.highestSeverity = Math.max(archive.highestSeverity, sessionSummary.maxAnomalySeverity || 0);

  if (skinProgress) {
    skinProgress.sessionsPlayed += 1;
    skinProgress.totalAnomaliesTriggered += sessionSummary.anomaliesTriggeredTotal || 0;
    skinProgress.totalLogsUnlocked += unlockedLogIds.length;
    skinProgress.highestSeverity = Math.max(skinProgress.highestSeverity, sessionSummary.maxAnomalySeverity || 0);
  }

  for (const id of sessionSummary.anomalyIds || []) {
    archive.encounteredAnomalies[id] = (archive.encounteredAnomalies[id] || 0) + 1;
    if (skinProgress) {
      skinProgress.encounteredAnomalies[id] = (skinProgress.encounteredAnomalies[id] || 0) + 1;
    }
  }
  for (const id of unlockedLogIds) {
    archive.unlockedLogs[id] = true;
    if (skinProgress) skinProgress.unlockedLogs[id] = true;
  }
  saveArchive(archive);
  return archive;
}

export function getArchiveSkinProgress(archive, skinId, anomalyCatalog = []) {
  const normalized = normalizeArchive(archive);
  const progress = normalized.skins[skinId] || cloneDefaultSkinProgress();
  const totalAnomalies = anomalyCatalog.length;
  const encounteredCount = Object.keys(progress.encounteredAnomalies).length;
  const unlockedLogsCount = Object.keys(progress.unlockedLogs).length;

  return {
    skinId,
    sessionsPlayed: progress.sessionsPlayed,
    encounteredCount,
    unlockedLogsCount,
    totalAnomalies,
    completionRate: totalAnomalies ? encounteredCount / totalAnomalies : 0,
    logCompletionRate: totalAnomalies ? unlockedLogsCount / totalAnomalies : 0,
    highestSeverity: progress.highestSeverity,
    totalAnomaliesTriggered: progress.totalAnomaliesTriggered,
  };
}
