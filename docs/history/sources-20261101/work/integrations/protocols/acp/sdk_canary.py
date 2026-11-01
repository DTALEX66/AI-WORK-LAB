"""Real ACP SDK stdio transport canary, using a synthetic peer and zero LLM calls.

Uses agentclientprotocol/python-sdk (Apache-2.0) as a dependency.
This proves protocol transport only, NOT Codex/Hermes/DSH integration.
No tools, private files, credentials, or user sessions are exposed to the peer.
"""
import asyncio
import json
import os
import sys
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

from acp import (Agent, Client, PROTOCOL_VERSION, InitializeResponse,
                 NewSessionResponse, PromptResponse, connect_to_agent, run_agent)
from acp.schema import AgentMessageChunk, ClientCapabilities, TextContentBlock


class SyntheticPeer(Agent):
    def on_connect(self, conn):
        self.conn = conn

    async def initialize(self, protocol_version, **kwargs):
        return InitializeResponse(protocol_version=protocol_version)

    async def new_session(self, cwd, **kwargs):
        return NewSessionResponse(session_id=uuid4().hex)

    async def prompt(self, session_id, prompt, **kwargs):
        for block in prompt:
            await self.conn.session_update(session_id=session_id,
                update=AgentMessageChunk(session_update='agent_message_chunk',
                    content=TextContentBlock(type='text', text=block.text)))
        return PromptResponse(stop_reason='end_turn')


class ReadOnlyClient(Client):
    def __init__(self):
        self.chunks = []

    async def session_update(self, session_id, update, **kwargs):
        if isinstance(update, AgentMessageChunk):
            self.chunks.append((session_id, update.content.text))


async def canary():
    root = Path(__file__).resolve().parents[3]
    scratch = root / '.project-local/runs/acp-sdk-canary'
    scratch.mkdir(parents=True, exist_ok=True)
    # A minimal process environment; do not forward API credentials.
    env = {key: os.environ[key] for key in ('PATH', 'SYSTEMROOT', 'WINDIR') if key in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1', TMP=str(scratch), TEMP=str(scratch), TMPDIR=str(scratch))
    proc = await asyncio.create_subprocess_exec(sys.executable, str(Path(__file__).resolve()),
        '--synthetic-peer', stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, cwd=scratch, env=env)
    try:
        client = ReadOnlyClient()
        conn = connect_to_agent(client, proc.stdin, proc.stdout)
        initialized = await asyncio.wait_for(conn.initialize(
            protocol_version=PROTOCOL_VERSION, client_capabilities=ClientCapabilities()), 10)
        session = await asyncio.wait_for(conn.new_session(cwd=str(scratch), mcp_servers=[]), 10)
        response = await asyncio.wait_for(conn.prompt(session_id=session.session_id,
            prompt=[TextContentBlock(type='text', text='WORK_LAB_ACP_TRANSPORT_CANARY')]), 10)
        assert initialized.protocol_version == PROTOCOL_VERSION
        assert session.session_id
        assert response.stop_reason == 'end_turn'
        assert client.chunks == [(session.session_id, 'WORK_LAB_ACP_TRANSPORT_CANARY')]
        return {'status': 'PROTOCOL_TRANSPORT_PASS', 'sdk': version('agent-client-protocol'),
                'protocol_version': PROTOCOL_VERSION, 'separate_process': True,
                'stream_chunks': len(client.chunks), 'model_calls': 0,
                'native_executor_verified': False}
    finally:
        # Only this canary's child process is terminated. This is cleanup,
        # not evidence of native agent cancellation support.
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), 5)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()


if __name__ == '__main__':
    if '--synthetic-peer' in sys.argv:
        asyncio.run(run_agent(SyntheticPeer()))
    else:
        print(json.dumps(asyncio.run(canary()), ensure_ascii=False))
