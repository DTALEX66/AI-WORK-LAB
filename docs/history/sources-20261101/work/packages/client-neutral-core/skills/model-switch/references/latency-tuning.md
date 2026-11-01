# Hermes / Kimi latency tuning (historical benchmark)

Use this when the user says Hermes or Kimi feels slow, hangs, or needs a measured
comparison. The observations below are examples, not a portable default or a
recommended model. Every current run must use a model ID explicitly selected by
the user and record that ID in its evidence.

## Official Kimi facts checked 2026-07-20

- Kimi K3 is the flagship/deep-reasoning model with 1M context. It always reasons and supports top-level `reasoning_effort` values: `low`, `high`, `max`.
- K3's documented default reasoning effort is `max`, which can be much slower for normal chat.
- Kimi K2.7 Code is the dedicated coding model with 256k context.
- `kimi-k2.7-code-highspeed` is Kimi's official high-speed K2.7 Code variant, documented around ~180 tok/s and up to ~260 tok/s in short-context scenarios, subject to capacity fluctuation.
- Kimi docs recommend reducing tool inventory: do not send every tool definition when many tools exist; dynamically load/search tools where possible.

## Historical environment snapshot

The following values describe an old measured environment only. They must not be
copied into the portable config or treated as current defaults. Use the user's
selected model and current official provider documentation instead.

```yaml
display:
  streaming: true
agent:
  reasoning_effort: low
model:
  max_tokens: 8192
```

Rationale:

- `display.streaming=true`: removes the "卡住无输出" feeling by showing tokens as they arrive.
- `agent.reasoning_effort=low`: makes K3 use official low reasoning effort for normal turns; raise only when needed.
- `model.max_tokens=8192`: prevents accidental 20k+ token runaway outputs that make the UI look frozen.

## User slash commands

```text
/切换KIMI       -> kimi-k3, high quality/default
/切换KIMI稳     -> kimi-k3, same as default
/切换KIMI快     -> kimi-k2.7-code
/切换KIMI极速   -> kimi-k2.7-code-highspeed, official speed lane
```

After changing model/config in Desktop, tell the user to `/reset` or fully restart Hermes Desktop if the backend process is already running.

## Measured smoke benchmark pattern

Run with real API, never print keys:

```bash
python - <<'PY'
import os, time, json
from openai import OpenAI
from hermes_cli.env_loader import load_hermes_dotenv
load_hermes_dotenv()
client = OpenAI(
    api_key=os.getenv('KIMI_API_KEY') or os.getenv('KIMI_CN_API_KEY'),
    base_url=os.getenv('KIMI_BASE_URL') or 'https://api.moonshot.cn/v1',
    default_headers={'Accept-Encoding': 'gzip, deflate'},
    max_retries=0,
)
for model, kw in [
    ('kimi-k3', {'reasoning_effort': 'low'}),
    ('kimi-k3', {'reasoning_effort': 'high'}),
    ('kimi-k3', {'reasoning_effort': 'max'}),
    ('kimi-k2.7-code', {}),
    ('kimi-k2.7-code-highspeed', {}),
]:
    t0 = time.perf_counter(); first = None; chunks = 0; chars = 0; err = None
    try:
        stream = client.chat.completions.create(
            model=model, temperature=1, stream=True,
            messages=[{'role': 'user', 'content': 'Reply exactly: SPEED_OK'}],
            **kw,
        )
        for ch in stream:
            chunks += 1
            delta = ch.choices[0].delta if ch.choices else None
            content = getattr(delta, 'content', None) if delta else None
            reasoning = getattr(delta, 'reasoning_content', None) if delta else None
            if (content or reasoning) and first is None:
                first = time.perf_counter()
            if content:
                chars += len(content)
    except Exception as e:
        err = type(e).__name__ + ': ' + str(e)[:160]
    t1 = time.perf_counter()
    print(json.dumps({
        'model': model, **kw,
        'first_token_s': round((first or t1) - t0, 2),
        'total_s': round(t1 - t0, 2), 'chunks': chunks, 'chars': chars, 'error': err,
    }, ensure_ascii=False))
PY
```

Sample verified 2026-07-20:

```text
kimi-k3 low: first_token_s 2.38, total_s 3.41
kimi-k3 high: first_token_s 2.14, total_s 2.97
kimi-k3 max: first_token_s 2.94, total_s 9.05
kimi-k2.7-code: first_token_s 0.69, total_s 1.18
kimi-k2.7-code-highspeed: first_token_s 0.55, total_s 0.55
```

## Brotli caveat

Keep the Kimi/Moonshot client header mitigation:

```text
Accept-Encoding: gzip, deflate
```

This avoids `brotli: decoder process called with data when 'can_accept_more_data()' is False` on large streaming responses.
