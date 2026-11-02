#!/usr/bin/env python3
"""U19 deeper diagnosis (local, REAL): launch app.exe with U19 CDP env; poll
process liveness, CDP /json/list, and ALL top-level windows of the pid
(visible AND hidden) with titles. Read-only; writes nothing outside task-runtime."""
import ctypes, json, os, socket, subprocess, sys, time
from ctypes import wintypes

repo = r"D:/All projects/WORK-LAB"
OBS = os.path.join(repo, "apps/observer")
exe = os.path.join(OBS, "src-tauri", "target", "release", "app.exe")

s = socket.socket(); s.bind(("127.0.0.1", 0)); cdp = s.getsockname()[1]; s.close()

env = dict(os.environ)
env["NO_AUTO_UPDATE"] = "1"
env["WORK_LAB_U19_CDP_PORT"] = str(cdp)

import threading, urllib.request, pathlib
sys.path.insert(0, os.path.join(repo, "services", "orchestration"))
sys.path.insert(0, os.path.join(repo, "packages", "client-neutral-core", "scripts"))
from sidecar import WorkflowSidecar, create_server
rr = pathlib.Path(os.path.join(repo, ".hermes", "task-runtime", "worklab-convergence-20260921", "diag_sidecar"))
rr.mkdir(parents=True, exist_ok=True)
sidecar = WorkflowSidecar(pathlib.Path(repo), rr)
server = create_server(sidecar, "127.0.0.1", 0)
bport = server.server_port
threading.Thread(target=server.serve_forever, daemon=True).start()
env["WORK_LAB_OBSERVER_API_URL"] = f"http://127.0.0.1:{bport}/api/v1/snapshot"

app = subprocess.Popen([exe], cwd=os.path.join(OBS, "src-tauri"), env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(f"pid={app.pid} cdp_port={cdp} backend={bport}")

user32 = ctypes.windll.user32
user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

def windows_of(pid):
    res = []
    def cb2(h, l):
        wp = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value == pid:
            tlen = user32.GetWindowTextLengthW(h)
            buf = ctypes.create_unicode_buffer(tlen + 1)
            user32.GetWindowTextW(h, buf, tlen + 1)
            vis = user32.IsWindowVisible(h)
            res.append((h, buf.value, vis))
        return True
    user32.EnumWindows(EnumProc(cb2), 0)
    return res

def cdp_list():
    try:
        sk = socket.create_connection(("127.0.0.1", cdp), timeout=3)
    except Exception as e:
        return f"conn-refused ({type(e).__name__})"
    try:
        sk.sendall(f"GET /json/list HTTP/1.1\r\nHost: 127.0.0.1:{cdp}\r\nConnection: close\r\n\r\n".encode())
        data = b""
        while True:
            c = sk.recv(65536)
            if not c: break
            data += c
        head, _, body = data.partition(b"\r\n\r\n")
        status = head.split(b"\r\n",1)[0].decode()
        if "200" not in status:
            return f"HTTP {status}"
        return json.loads(body.decode("utf-8","replace"))
    finally:
        sk.close()

for i in range(24):
    alive = app.poll() is None
    w = windows_of(app.pid)
    c = cdp_list()
    cstr = json.dumps(c) if isinstance(c, list) else str(c)
    print(f"t={i*5:>3}s alive={alive} windows={[(hex(a), t, vis) for a,t,vis in w]} cdp={cstr[:300]}")
    if alive and isinstance(c, list) and any(x.get("type")=="page" for x in c):
        print("CDP page target appeared at t=", i*5)
        break
    if not alive:
        print("process exited early, returncode", app.returncode)
        break
    time.sleep(5)

app.terminate()
try: app.wait(timeout=8)
except Exception: app.kill()
server.shutdown(); server.server_close()
print("done")
