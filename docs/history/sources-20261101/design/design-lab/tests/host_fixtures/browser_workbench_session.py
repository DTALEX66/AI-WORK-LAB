# SPDX-License-Identifier: MIT
"""Start an isolated real-browser fixture; keep temporary access only in memory."""
import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from design_lab.service import ProjectService
from design_lab.http_service import make_server


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cli',required=True)
    parser.add_argument('--live-project',action='store_true',help='use the owning project stores and native guards')
    args=parser.parse_args()
    base=ROOT/'.project-local/task-runtime/browser-fixture'
    base.mkdir(parents=True,exist_ok=True)
    context=nullcontext(ROOT) if args.live_project else tempfile.TemporaryDirectory(dir=base)
    with context as directory:
        owner=Path(directory)
        if not args.live_project:(owner/'AGENTS.md').write_text('# Isolated browser fixture\n',encoding='utf-8')
        os.environ['PROJECT_LOCAL_ROOT']=str(owner/'.project-local')
        access=secrets.token_hex(32)
        server=make_server(ProjectService(owner),access)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def cli(*command):
            result=subprocess.run([shutil.which('node'),args.cli,'-s=design-r5',*command],
                cwd=ROOT,env=os.environ,capture_output=True,text=True,encoding='utf-8',timeout=40)
            if result.returncode or '### Error' in result.stdout:
                raise RuntimeError('BROWSER_ACTION_FAILED')
            return result.stdout.replace(access,'[REDACTED]')
        try:
            print(cli('goto',f'http://127.0.0.1:{server.server_port}/workbench'),flush=True)
            # Atomic fill+submit avoids snapshots of a populated password field.
            # The public login controls were inspected before this operation.
            code="async (page) => { await page.getByRole('textbox',{name:'临时访问令牌'}).fill("+json.dumps(access)+"); await page.getByRole('button',{name:'连接服务',exact:true}).click(); await page.getByText('选择或新建项目。',{exact:true}).waitFor(); }"
            cli('run-code',code)
            print(cli('snapshot'),flush=True)
            print('BROWSER_FIXTURE_AUTHENTICATED port='+str(server.server_port),flush=True)
            # API execution may supply an already-closed stdin. Keep a bounded
            # interactive test window instead of treating EOF as user shutdown.
            try:threading.Event().wait(300)
            except KeyboardInterrupt:pass
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':main()
