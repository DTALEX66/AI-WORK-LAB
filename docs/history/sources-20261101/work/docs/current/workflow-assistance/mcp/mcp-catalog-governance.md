# MCP Catalog Governance

Workflow-assistance 默认 MCP 保持少量、稳定、可验证。新增 MCP 先进入候选审计，不直接写入 `config/config.yaml`。

## Canonical audit command

```bash
python packages/client-neutral-core/scripts/mcp_candidate_audit.py candidate.yaml
```

生成候选模板：

```bash
python packages/client-neutral-core/scripts/mcp_candidate_audit.py --write-template .project-local/artifacts/mcp-candidate.yaml
```

候选文件建议放在项目内 Git-ignored 的 `.project-local/artifacts/` 或 PR 讨论附件中；不要把含真实 token、私有服务名、客户数据或内部 URL 的候选文件提交到仓库。

## Candidate schema

```yaml
schema_version: 1
name: example-mcp
status: candidate
default_enable: false
source:
  package: "@scope/example-mcp@1.2.3"
  repository: "https://github.com/example/example-mcp"
  license: MIT
  version: "1.2.3"
purpose: "What native Hermes cannot already do."
distinct_advantage: "Why this is better than native Hermes tools for the target workflow."
data_external: true
permissions:
  filesystem: none
  network: public docs API
  browser: none
  credentials: []
required_env: []
overlaps_native_tools: []
smoke:
  command: "hermes mcp test example-mcp"
  status: not_run
  evidence: "Run before enabling by default."
prompt_schema_budget:
  measured: false
  command: "hermes prompt-size --json"
  delta_tokens: null
```

## Blocking rules

The audit fails closed when a candidate:

- has no pinned package/version, or uses `latest`;
- lacks source repository, license, purpose, distinct advantage, data externality, or permission fields;
- overlaps Hermes native `file`, `memory`, `browser`, `computer_use`, `web`, `web_search`, `search`, or `session_search` capabilities without a distinct advantage;
- requests `default_enable: true` from the candidate file;
- claims `smoke.status: pass` without command evidence;
- asks for default enablement without smoke pass and prompt schema budget evidence.

The candidate audit can pass for an optional MCP with `smoke.status: not_run`; that means "documented candidate", not "safe default". To become a default MCP, a separate code change must update `config/config.yaml`, docs, governance tests, and CI evidence.

## Default-enable policy

Default enablement for a new candidate MCP still requires all existing Workflow MCP Stack gates; the existing Context7 portable baseline is pinned to the documented official package/version:

1. Native Hermes tools cannot cover the use case.
2. Candidate version and license/source are pinned; the Context7 portable baseline is pinned as well.
3. `hermes mcp test <name>` passes.
4. Data externality, filesystem/network/browser permissions and credential needs are documented.
5. Tool schema prompt-size delta is measured.
6. `config/config.yaml`, README, docs and governance tests are updated together.

## Native overlap map

| Native Hermes capability | Candidate MCP risk |
|---|---|
| `file` | broad filesystem exposure, duplicate edit/read surface |
| `memory` | duplicate long-term memory authority |
| `browser` / `computer_use` | larger browser/device permission surface |
| `web` / `web_search` | duplicate search wrappers, possible data exfiltration |
| `session_search` | duplicate conversation-history access |

If a candidate overlaps one of these, the audit file must explain the unique benefit in `distinct_advantage` and list the overlap in `overlaps_native_tools`.

## Output markers

Pass:

```text
MCP_CANDIDATE_AUDIT_PASS candidate=<name>
```

Fail:

```text
MCP_CANDIDATE_AUDIT_FAIL candidate=<name>
blocker:<code>:<message>
```

These markers are for candidate evaluation only. They do not prove that a server is configured, running, safe, or enabled in live Hermes.
