#!/usr/bin/env python3
"""U19 control: does app.exe survive WITHOUT the U19 CDP env? 30s poll.
Captures app stderr to task-runtime for crash diagnosis."""
import ctypes, os, socket, subprocess, sys, time, threading, pathlib
from ctypes import wintypes

repo = r"D:/All projects/WORK-LAB"
OBS = os.path.join(repo, "apps/observer")
exe = os.path.join(OBS, "src-tauri", "target", "release", "app.exe")
base = os.path.join(repo, ".hermes", "task-runtime", "worklab-convergence-20260921")
base2 = os.path.join(base, "ctrl_sidecar"); pathlib.Path(base2).mkdir(parents=True, exist_ok=True)

sys.path.insert(0, os.path.join(repo, "services", "orchestration"))
sys.path.insert(0, os.path.join(repo, "packages", "client-neutral-core", "scripts"))
from sidecar import WorkflowSidecar, create_server
server = create_server(WorkflowSidecar(pathlib.Path(repo), pathlib.Path(base2)), "127.0.0.1", 0)
bport = server.server_port
threading.Thread(target=server.serve_forever, daemon=True).start()

user32 = ctypes.windll.user32
user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
EP = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
def windows_of(pid):
    res = []
    def cb2(h, l):
        wp = ctypes.c_ulong(); user32.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value == pid:
            buf = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(h) + 1)
            user32.GetWindowTextW(h, buf, user32.GetWindowTextLengthW(h) + 1)
            res.append((hex(h), buf.value, user32.IsWindowVisible(h)))
        return True
    user32.EnumWindows(EP(cb2), 0)
    return res

import json
for tag, extra_env in [("no-cdp-env", {}), ("with-cdp-env", {"WORK_LAB_U19_CDP_PORT": "19222"})]:
    env = dict(os.environ)
    env["NO_AUTO_UPDATE"] = "1"
    env["WORK_LAB_OBSERVER_API_URL"] = f"http://127.0.0.1:{bport}/api/v1/snapshot"
    env.update(extra_env)
    errf = open(os.path.join(base, f"ctrl_{tag}_stderr.log"), "wb")
    app = subprocess.Popen([exe], cwd=os.path.join(OBS, "src-tauri"), env=env, stderr=errf, stdout=subprocess.DEVNULL)
    print(f"=== {tag}: pid={app.pid} ===")
    for i in range(6):
        rc = app.poll()
        w = windows_of(app.pid) if rc is None else []
        print(f"t={i*5:>2}s rc={'-' if rc is None else rc} windows={[(t,v) for _,t,v in w]}")
        if rc is not None:
            break
        time.sleep(5)
    if app.poll() is None:
        app.terminate()
        try: app.wait(timeout=8)
        except Exception: app.kill()
    errf.close()
server.shutdown(); server.server_close()
print("done")
