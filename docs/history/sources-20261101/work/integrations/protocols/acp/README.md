# ACP SDK transport canary

Optional direct reuse of the official agentclientprotocol/python-sdk, Apache-2.0.
Pinned SDK: agent-client-protocol==0.12.1. Install into an isolated environment;
run sdk_canary.py from that environment. This dependency is not enabled globally.

The canary creates one synthetic peer process, initializes ACP, creates a session,
sends a prompt and checks the streamed response. Zero model calls and no real
executor integration. No credentials or filesystem/tool capabilities are passed.
Transport success is not evidence of native execution, cancellation or recovery.

Production follow-up: confirm each executor's native protocol/version; wire one
actual supported transport into the existing adapter, with explicit capabilities
and failure/readback tests. Do not replace native runtimes or silently add wrappers.

Source: https://github.com/agentclientprotocol/python-sdk
