const PROVIDER_ROWS = [
  ['GPT / Codex', 1_860_000, 1_040_000, 742],
  ['Kimi', 760_000, 440_000, 251],
  ['DeepSeek', 250_000, 64_000, 208],
  ['Other', 250_000, 171_000, 83],
];

export const demoProviders = PROVIDER_ROWS.map(([provider, input, output, requests]) => ({
  provider,
  input_tokens: input,
  output_tokens: output,
  total_tokens: input + output,
  requests,
}));

export const demoModels = [
  { provider: 'GPT / Codex', model: 'gpt-5.5-codex', input_tokens: 1_100_000, output_tokens: 700_000, cached_input_tokens: 980_000, reasoning_tokens: 210_000, total_tokens: 1_800_000, requests: 410 },
  { provider: 'GPT / Codex', model: 'gpt-5.1-codex-mini', input_tokens: 760_000, output_tokens: 340_000, cached_input_tokens: 640_000, reasoning_tokens: 120_000, total_tokens: 1_100_000, requests: 332 },
  { provider: 'Kimi', model: 'kimi-for-coding', input_tokens: 760_000, output_tokens: 440_000, cached_input_tokens: 520_000, reasoning_tokens: 90_000, total_tokens: 1_200_000, requests: 251 },
  { provider: 'DeepSeek', model: 'deepseek-v4-flash', input_tokens: 250_000, output_tokens: 64_000, cached_input_tokens: 180_000, reasoning_tokens: 24_000, total_tokens: 314_000, requests: 208 },
  { provider: 'Other', model: 'qwen3-coder', input_tokens: 250_000, output_tokens: 171_000, cached_input_tokens: 120_000, reasoning_tokens: 36_000, total_tokens: 421_000, requests: 83 },
];

const DAYS = [
  ['2026-10-05', 210_000],
  ['2026-10-06', 180_000],
  ['2026-10-07', 240_000],
  ['2026-10-08', 260_000],
  ['2026-10-09', 230_000],
  ['2026-10-10', 300_000],
  ['2026-10-11', 280_000],
  ['2026-10-12', 340_000],
  ['2026-10-13', 310_000],
  ['2026-10-14', 360_000],
  ['2026-10-15', 420_000],
  ['2026-10-16', 390_000],
  ['2026-10-17', 450_000],
  ['2026-10-18', 865_000],
].map(([day, total_tokens]) => ({ day, total_tokens, requests: Math.round(total_tokens / 3800) }));

const sum = (key) => demoProviders.reduce((total, item) => total + item[key], 0);

export const demoSnapshot = {
  source: '示例数据 · 不读取本机文件',
  scanned_files: 38,
  recognized_requests: sum('requests'),
  unknown_records: 3,
  input_tokens: sum('input_tokens'),
  output_tokens: sum('output_tokens'),
  cached_input_tokens: 1_940_000,
  reasoning_tokens: 610_000,
  total_tokens: sum('total_tokens'),
  providers: demoProviders,
  models: demoModels,
  days: DAYS,
  updated_at: Math.floor(Date.now() / 1000),
  confidence: 'exact',
  notice: null,
  file_sizes: {},
  demo: true,
};

export const emptyDemoSnapshot = {
  source: '示例数据 · 空源',
  scanned_files: 0,
  recognized_requests: 0,
  unknown_records: 0,
  input_tokens: 0,
  output_tokens: 0,
  cached_input_tokens: 0,
  reasoning_tokens: 0,
  total_tokens: 0,
  providers: [],
  models: [],
  days: [],
  updated_at: Math.floor(Date.now() / 1000),
  confidence: 'unknown',
  notice: null,
  file_sizes: {},
  demo: true,
};
