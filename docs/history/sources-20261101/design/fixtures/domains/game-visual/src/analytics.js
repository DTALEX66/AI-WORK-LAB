export const ANALYTICS_EVENTS = Object.freeze([
  'game_start',
  'game_over',
  'revive_ad_start',
  'revive_ad_reward',
  'hidden_log_ad_start',
  'hidden_log_unlock',
  'fake_ending_trigger',
  'action_click',
  'anomaly_trigger',
]);

export const ANALYTICS_SCHEMA_VERSION = 'minigame/analytics/v1';

const SENSITIVE_KEYS = new Set([
  'token',
  'password',
  'secret',
  'cookie',
  'auth',
  'prompt',
  'response',
]);

const EVENT_SET = new Set(ANALYTICS_EVENTS);

export function createConsoleAnalyticsSink(logger = console) {
  return (event) => {
    logger.log('[analytics]', event.name, event);
  };
}

export function createAnalyticsSink({ environment = 'development', logger = console, transport } = {}) {
  if (environment === 'development') {
    return createConsoleAnalyticsSink(logger);
  }
  if (environment !== 'production') {
    throw new Error(`Unknown analytics environment: ${environment}`);
  }
  if (typeof transport !== 'function') {
    throw new TypeError('production analytics transport must be a function');
  }
  return (event) => transport({
    ...event,
    schema_version: ANALYTICS_SCHEMA_VERSION,
  });
}

let analyticsSink = createAnalyticsSink({ environment: 'development' });

export function setAnalyticsSink(sink) {
  if (typeof sink !== 'function') {
    throw new TypeError('analytics sink must be a function');
  }
  analyticsSink = sink;
}

export function resetAnalyticsSink() {
  analyticsSink = createConsoleAnalyticsSink();
}

export function trackEvent(name, payload = {}, options = {}) {
  if (!EVENT_SET.has(name)) {
    throw new Error(`Unknown analytics event: ${name}`);
  }
  for (const key of Object.keys(payload)) {
    if (SENSITIVE_KEYS.has(key.toLowerCase())) {
      throw new Error(`Sensitive analytics payload key: ${key}`);
    }
  }

  const now = options.now || Date.now;
  const event = {
    name,
    ts: now(),
    ...payload,
    schema_version: ANALYTICS_SCHEMA_VERSION,
  };

  analyticsSink(event);
  return event;
}
