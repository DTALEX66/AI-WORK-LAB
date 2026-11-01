import { displayCompact, displayFull, escapeHtml } from './hudModel.js';

const countLabel = (value) => (value === null || value === undefined ? '—' : String(value));

function segmentsHtml(segments) {
  return segments
    .filter((segment) => segment.value > 0)
    .map((segment) => `<i style="width:${segment.pct.toFixed(2)}%;background:${segment.color}" title="${escapeHtml(segment.label)} ${displayFull(segment.value)}"></i>`)
    .join('');
}

function legendHtml(segments) {
  return segments
    .filter((segment) => segment.value > 0)
    .map((segment) => `<span class="hud-legend-item"><i style="background:${segment.color}"></i>${escapeHtml(segment.label)} <b>${displayCompact(segment.value)}</b><small>${Math.round(segment.pct)}%</small></span>`)
    .join('');
}

function sparkHtml(spark, accent) {
  if (!spark.length) return '<span class="hud-muted">暂无趋势</span>';
  return spark
    .map((item, index) => `<i style="height:${item.height.toFixed(1)}%;background:${accent};opacity:${index === spark.length - 1 ? 1 : 0.55}" title="${escapeHtml(item.day)} · ${displayCompact(item.value)}"></i>`)
    .join('');
}

function modelsHtml(models, providerTotal) {
  if (!models.length) return '<span class="hud-muted">暂无模型明细</span>';
  const max = Math.max(...models.map((item) => Number(item.total_tokens) || 0), 1);
  return models
    .map((item) => {
      const width = Math.max(2, ((Number(item.total_tokens) || 0) / max) * 100);
      const share = providerTotal > 0 ? Math.round(((Number(item.total_tokens) || 0) / providerTotal) * 100) : null;
      return `<div class="hud-model-row"><span class="hud-model-name">${escapeHtml(item.model || 'unknown-model')}</span><b>${displayCompact(Number(item.total_tokens) || 0, 1)}</b><span class="hud-model-bar"><i style="width:${width.toFixed(1)}%"></i></span><small>${share === null ? '—' : `${share}%`}</small></div>`;
    })
    .join('');
}

function agentHtml(provider, selected) {
  const dimensions = provider.meta;
  const label = `${provider.provider}，份额 ${provider.shareLabel}，${displayFull(provider.value)} tokens，${displayFull(provider.requests, provider.requests)} requests`;
  return `<button type="button" class="hud-agent${selected ? ' selected' : ''}" data-provider="${escapeHtml(provider.provider)}" aria-pressed="${selected}" aria-label="${escapeHtml(label)}" style="--accent:${dimensions.accent};--accent-soft:${dimensions.soft}">
    <span class="hud-ring" aria-hidden="true">
      <svg viewBox="0 0 96 96" focusable="false">
        <circle class="hud-ring-track" cx="48" cy="48" r="42"></circle>
        <circle class="hud-ring-arc" cx="48" cy="48" r="42" stroke-dasharray="${provider.ring.dasharray}" transform="rotate(-90 48 48)"></circle>
      </svg>
      <span class="hud-bot"><i class="hud-eye l"></i><i class="hud-eye r"></i></span>
    </span>
    <span class="hud-share">份额 ${provider.shareLabel}</span>
    <span class="hud-agent-name">${escapeHtml(provider.provider)}</span>
    <span class="hud-agent-total">${provider.totalLabel}</span>
    <span class="hud-agent-sub">${displayFull(provider.requests, provider.requests)} requests</span>
    <span class="hud-seg" aria-hidden="true">${segmentsHtml(provider.segments)}</span>
  </button>`;
}

function emptyHtml() {
  return `<div class="hud-empty" role="status">
    <span class="hud-empty-ring" aria-hidden="true"><span></span></span>
    <span><strong>尚未发现 usage</strong><small>未知不会显示为 0。在仪表盘确认数据源并开始监控后，这里会出现 provider 环。</small></span>
  </div>`;
}

export function detailHtml(model, selectedName = null) {
  const provider = model.providers.find((item) => item.provider === selectedName) || model.providers[0] || null;
  if (!provider) {
    return `<section class="hud-detail hud-detail-empty" aria-live="polite">
      <div><span class="hud-detail-title">等待 usage</span><p class="hud-muted">监控已就绪；未识别到明确 token 字段时保持“—”，不会估算、也不会把未知写成 0。</p></div>
      <div class="hud-detail-side"><div class="hud-side-head"><span>近 14 天</span><span>全部来源</span></div><div class="hud-spark">${sparkHtml(model.spark, '#8e8e93')}</div></div>
    </section>`;
  }
  const providerTotal = provider.value;
  return `<section class="hud-detail" aria-live="polite">
    <div class="hud-detail-main">
      <div class="hud-detail-head">
        <span class="hud-detail-title">${escapeHtml(provider.provider)}</span>
        <span class="hud-detail-badge">份额 ${provider.shareLabel}</span>
      </div>
      <div class="hud-detail-total">${provider.totalLabel}<small>tokens</small></div>
      <div class="hud-detail-grid">
        <div><span>输入</span><b>${displayCompact(provider.input_tokens, provider.requests)}</b></div>
        <div><span>输出</span><b>${displayCompact(provider.output_tokens, provider.requests)}</b></div>
        <div><span>请求</span><b>${displayFull(provider.requests, provider.requests)}</b></div>
      </div>
      <div class="hud-seg hud-seg-lg" aria-hidden="true">${segmentsHtml(provider.segments)}</div>
      <div class="hud-legend">${legendHtml(provider.segments)}</div>
    </div>
    <div class="hud-detail-side">
      <div class="hud-side-head"><span>近 14 天</span><span>全部来源</span></div>
      <div class="hud-spark">${sparkHtml(model.spark, provider.meta.accent)}</div>
      <div class="hud-models-head"><span>模型</span><span>${escapeHtml(provider.provider)}</span></div>
      <div class="hud-models">${modelsHtml(model.models, providerTotal)}</div>
    </div>
  </section>`;
}

export function renderHud(model, uiState = {}) {
  const mode = uiState.mode === 'compact' ? 'compact' : 'full';
  const status = model.status;
  const glow = model.providers.length
    ? model.providers.map((item) => item.meta.accent)
    : ['#3a3a3f', '#2c2c31', '#3a3a3f', '#2c2c31'];
  const style = `--glow-a:${glow[0]};--glow-b:${glow[1] || glow[0]};--glow-c:${glow[2] || glow[0]};--glow-d:${glow[3] || glow[0]};`;
  const actionLabel = uiState.historical ? '本次新增' : '历史累计';
  const monitorLabel = uiState.started ? '停止监控' : '开始监控';
  const demoBadge = model.demo ? '<span class="hud-demo">DEMO</span>' : '';
  const agents = model.providers.length
    ? model.providers.map((provider) => agentHtml(provider, provider.provider === model.selectedProvider)).join('')
    : emptyHtml();
  const actions = `<button type="button" data-hud-action="dashboard">仪表盘</button>
    <button type="button" data-hud-action="mode">${mode === 'compact' ? '展开' : '紧凑'}</button>
    <button type="button" class="hud-action-extra" data-hud-action="history">${actionLabel}</button>
    ${model.demo ? demoBadge : `<button type="button" class="hud-action-extra" data-hud-action="refresh">刷新</button>
    <button type="button" class="hud-action-extra primary" data-hud-action="monitor">${monitorLabel}</button>`}`;
  return `<div class="hud-stage" data-state="${status.key}" data-mode="${mode}">
    <div class="hud-notch" aria-hidden="true"><span class="hud-notch-dot"></span><span>HERMES HUD</span></div>
    <section class="hud-panel${uiState.tick ? ' hud-tick' : ''}" data-state="${status.key}" style="${style}" aria-label="Hermes HUD">
      <span class="hud-top-glow" aria-hidden="true"></span>
      <header class="hud-top">
        <div class="hud-brand">
          <span class="hud-mark" aria-hidden="true"><i></i></span>
          <div><h1>Hermes HUD</h1><p>本地 usage · 只读 · 不上传</p></div>
        </div>
        <div class="hud-actions">${actions}</div>
        <div class="hud-hero">
          <div class="hud-total-block">
            <span class="hud-label">TOTAL TOKENS</span>
            <strong${model.totalLabel === '—' ? ' class="is-unknown"' : ''}>${model.totalLabel}</strong>
            <span class="hud-total-meta">${displayFull(model.requests, model.requests)} requests · ${countLabel(model.scannedFilesLabel)} files${model.unknownRecords ? ` · ${countLabel(model.unknownLabel)} unknown` : ''}</span>
          </div>
          <div class="hud-status" data-state="${status.key}" role="status" aria-live="polite">
            <span class="hud-status-dot" aria-hidden="true"></span>
            <span class="hud-status-text">${status.label}</span>
            <span class="hud-status-detail">${escapeHtml(status.detail)}</span>
          </div>
        </div>
      </header>
      <div class="hud-agents" role="group" aria-label="按 provider 的 token 份额">${agents}</div>
      ${detailHtml(model, model.selectedProvider)}
      <section class="hud-metrics">${model.metrics.map((metric) => `<article class="hud-metric"><span>${escapeHtml(metric.label)}</span><b>${escapeHtml(metric.value)}</b><small>${escapeHtml(metric.meta)}</small></article>`).join('')}</section>
      <footer class="hud-footer">
        <span class="hud-source" title="${escapeHtml(model.source)}">${escapeHtml(model.source)}</span>
        <span>${countLabel(model.scannedFilesLabel)} files · ${countLabel(model.unknownLabel)} unknown · ${model.updatedLabel}</span>
        <span>${model.demo ? '示例数据 · 不是真实 usage' : '只读本地 · 不上传 · 不估算'}</span>
      </footer>
    </section>
  </div>`;
}
