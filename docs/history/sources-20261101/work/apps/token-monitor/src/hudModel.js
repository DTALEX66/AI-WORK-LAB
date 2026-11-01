const CIRCUMFERENCE = 2 * Math.PI * 42;
const compactFormatter = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });
const fullFormatter = new Intl.NumberFormat('en-US');

export const PROVIDER_META = {
  'GPT / Codex': { accent: '#9b7cff', soft: '#e9e1ff', short: 'Codex' },
  DeepSeek: { accent: '#55d8ff', soft: '#d9f8ff', short: 'DeepSeek' },
  Kimi: { accent: '#ffb86b', soft: '#ffe7cc', short: 'Kimi' },
  Other: { accent: '#61e6a9', soft: '#d6ffe9', short: 'Other' },
};

const FALLBACK_META = { accent: '#8e8e93', soft: '#e5e5ea', short: 'Other' };

export function providerMeta(name) {
  return PROVIDER_META[name] || FALLBACK_META;
}

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char]);
}

export function isKnownNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function nonNegative(value) {
  return isKnownNumber(value) ? Math.max(0, value) : 0;
}

export function knownTotal(snapshot) {
  if (!snapshot) return null;
  const requests = nonNegative(snapshot.recognized_requests);
  const total = isKnownNumber(snapshot.total_tokens) ? snapshot.total_tokens : null;
  if (total !== null && (total > 0 || requests > 0)) return total;
  const providerSum = (snapshot.providers || []).reduce((sum, item) => sum + nonNegative(item && item.total_tokens), 0);
  if (providerSum > 0) return providerSum;
  return requests > 0 ? 0 : null;
}

export function knownMetric(snapshot, key) {
  if (!snapshot) return null;
  const requests = nonNegative(snapshot.recognized_requests);
  const value = snapshot[key];
  if (isKnownNumber(value) && (value > 0 || requests > 0)) return Math.max(0, value);
  return null;
}

export function formatCompact(value) {
  return isKnownNumber(value) ? compactFormatter.format(value) : '—';
}

export function formatFull(value) {
  return isKnownNumber(value) ? fullFormatter.format(value) : '—';
}

export function displayCompact(value, requests = 0) {
  if (!isKnownNumber(value)) return '—';
  return value === 0 && requests === 0 ? '—' : compactFormatter.format(value);
}

export function displayFull(value, requests = 0) {
  if (!isKnownNumber(value)) return '—';
  return value === 0 && requests === 0 ? '—' : fullFormatter.format(value);
}

export function displayCount(value, known) {
  return known && isKnownNumber(value) ? fullFormatter.format(value) : '—';
}

export function percentLabel(share) {
  if (!isKnownNumber(share)) return '—';
  const percent = share * 100;
  if (percent === 0) return '0%';
  if (percent < 1) return '<1%';
  return `${Math.round(percent)}%`;
}

export function providerShares(providers = []) {
  const rows = providers.map((item) => ({
    ...item,
    value: nonNegative(item && item.total_tokens),
  }));
  const total = rows.reduce((sum, item) => sum + item.value, 0);
  return rows.map((item) => ({
    ...item,
    share: total > 0 ? item.value / total : null,
  }));
}

function withPercentages(segments) {
  const total = segments.reduce((sum, item) => sum + item.value, 0);
  return segments.map((item) => ({
    ...item,
    pct: total > 0 ? (item.value / total) * 100 : 0,
  }));
}

export function splitProvider(provider) {
  const input = nonNegative(provider && provider.input_tokens);
  const output = nonNegative(provider && provider.output_tokens);
  const reported = nonNegative(provider && provider.total_tokens);
  const rest = Math.max(0, reported - input - output);
  const segments = [
    { key: 'input', label: '输入', value: input, color: 'var(--accent)' },
    { key: 'output', label: '输出', value: output, color: 'var(--accent-soft)' },
  ];
  if (rest > 0) segments.push({ key: 'other', label: '未分类', value: rest, color: '#8e8e93' });
  return withPercentages(segments);
}

// Cached input is a subset of input and reasoning is a subset of output.
// Splitting them keeps the five kinds additive instead of double counting.
export function splitAggregate(snapshot) {
  const input = nonNegative(snapshot && snapshot.input_tokens);
  const output = nonNegative(snapshot && snapshot.output_tokens);
  const cacheRead = Math.min(nonNegative(snapshot && snapshot.cached_input_tokens), input);
  const reasoning = Math.min(nonNegative(snapshot && snapshot.reasoning_tokens), output);
  const reported = nonNegative(snapshot && snapshot.total_tokens);
  const accounted = input + output;
  const rest = Math.max(0, reported - accounted);
  const segments = [
    { key: 'input', label: '输入', value: input - cacheRead, color: '#9b7cff' },
    { key: 'cache', label: '缓存读', value: cacheRead, color: '#55d8ff' },
    { key: 'output', label: '输出', value: output - reasoning, color: '#61e6a9' },
    { key: 'reasoning', label: '推理', value: reasoning, color: '#ffb86b' },
  ];
  if (rest > 0) segments.push({ key: 'other', label: '未分类', value: rest, color: '#8e8e93' });
  return withPercentages(segments);
}

export function ringGeometry(share, circumference = CIRCUMFERENCE) {
  if (!isKnownNumber(share)) {
    return { dasharray: `0 ${circumference}`, known: false };
  }
  const clamped = Math.min(1, Math.max(0, share));
  return { dasharray: `${clamped * circumference} ${circumference}`, known: true };
}

export function statusOf(state = {}, snapshot = null) {
  if (state.loading) return { key: 'scanning', label: 'SCANNING', detail: '正在读取本地数据源' };
  if (state.error) return { key: 'error', label: 'SOURCE ERROR', detail: String(state.error) };
  if (!state.started) return { key: 'paused', label: 'PAUSED', detail: state.pauseReason || '监控已暂停' };
  const requests = nonNegative(snapshot && snapshot.recognized_requests);
  if (requests === 0) {
    const baselineRequests = nonNegative(state.baseline && state.baseline.recognized_requests);
    if (state.started && baselineRequests > 0 && state.mode !== 'history') {
      return { key: 'waiting', label: 'LIVE', detail: '已连接；尚无新增 usage，切到历史累计查看已有记录' };
    }
    return { key: 'empty', label: 'NO USAGE', detail: '已连接，但没有发现明确 usage；未知不会显示为 0' };
  }
  if (snapshot && snapshot.confidence === 'exact') return { key: 'live', label: 'LIVE', detail: '只读本地数据源，不上传' };
  return { key: 'unknown', label: 'UNKNOWN', detail: '已发现记录，但无法确认 usage 精度' };
}

export function timestampMs(value) {
  if (!isKnownNumber(value) || value <= 0) return null;
  return value < 1e12 ? value * 1000 : value;
}

export function formatClock(value) {
  const ms = timestampMs(value);
  if (ms === null) return '—';
  return new Date(ms).toLocaleTimeString('zh-CN', { hour12: false });
}

export function activityRate(previousTotal, currentTotal, elapsedMs) {
  if (!isKnownNumber(previousTotal) || !isKnownNumber(currentTotal) || !isKnownNumber(elapsedMs) || elapsedMs <= 0) return null;
  const delta = currentTotal - previousTotal;
  if (delta < 0) return null;
  return (delta / elapsedMs) * 60000;
}

export function sparkSeries(days = [], limit = 14) {
  const rows = days.slice(-limit).map((item) => ({
    day: String(item && item.day ? item.day : ''),
    value: nonNegative(item && item.total_tokens),
  }));
  const max = rows.reduce((top, item) => Math.max(top, item.value), 0);
  return rows.map((item) => ({ ...item, height: max > 0 ? Math.max(4, (item.value / max) * 100) : 4 }));
}

export function topModels(models = [], provider = null, limit = 3) {
  const filtered = provider ? models.filter((item) => item && item.provider === provider) : models;
  return filtered
    .slice()
    .sort((a, b) => nonNegative(b && b.total_tokens) - nonNegative(a && a.total_tokens))
    .slice(0, limit);
}

export function buildHudModel({ snapshot = null, state = {}, previous = null, previousAt = null, now = Date.now(), selectedProvider = null } = {}) {
  const status = statusOf(state, snapshot);
  const total = knownTotal(snapshot);
  const requests = nonNegative(snapshot && snapshot.recognized_requests);
  const providers = providerShares((snapshot && snapshot.providers) || []).map((item) => ({
    ...item,
    meta: providerMeta(item.provider),
    ring: ringGeometry(item.share),
    shareLabel: percentLabel(item.share),
    totalLabel: displayCompact(item.value, requests),
    segments: splitProvider(item),
  }));
  const selected = providers.find((item) => item.provider === selectedProvider) || providers[0] || null;
  const totalLabel = displayCompact(total, requests);
  const scannedFilesLabel = displayCount(snapshot && snapshot.scanned_files, Boolean(snapshot));
  const unknownLabel = displayCount(snapshot && snapshot.unknown_records, Boolean(snapshot));
  const metrics = [
    { key: 'total', label: '总 Tokens', value: totalLabel, meta: `${displayFull(requests, requests)} 个 usage 记录` },
    { key: 'input', label: '输入', value: displayCompact(knownMetric(snapshot, 'input_tokens'), requests), meta: `缓存读 ${displayCompact(knownMetric(snapshot, 'cached_input_tokens'), requests)}` },
    { key: 'output', label: '输出', value: displayCompact(knownMetric(snapshot, 'output_tokens'), requests), meta: `推理 ${displayCompact(knownMetric(snapshot, 'reasoning_tokens'), requests)}` },
    { key: 'activity', label: '活动速率', value: activityLabel(previous, snapshot, previousAt, now, total), meta: `${scannedFilesLabel} 个文件` },
  ];
  return {
    status,
    total,
    totalLabel,
    requests,
    metrics,
    providers,
    selected,
    selectedProvider: selected ? selected.provider : null,
    aggregateSegments: splitAggregate(snapshot),
    spark: sparkSeries((snapshot && snapshot.days) || []),
    models: topModels((snapshot && snapshot.models) || [], selected ? selected.provider : null),
    source: (snapshot && snapshot.source) || (state && state.sourceText) || '尚未连接数据源',
    updatedLabel: formatClock(snapshot && snapshot.updated_at),
    scannedFiles: nonNegative(snapshot && snapshot.scanned_files),
    scannedFilesLabel,
    unknownLabel,
    unknownRecords: nonNegative(snapshot && snapshot.unknown_records),
    demo: Boolean(state.demo),
    empty: total === null || providers.length === 0,
  };
}

export function activityLabel(previous, current, previousAt, now, currentTotal) {
  if (!previous || !previousAt || !current) return '— / min';
  const previousTotal = knownTotal(previous);
  const rate = activityRate(previousTotal, currentTotal, now - previousAt);
  return rate === null ? '— / min' : `${compactFormatter.format(Math.round(rate))} / min`;
}
