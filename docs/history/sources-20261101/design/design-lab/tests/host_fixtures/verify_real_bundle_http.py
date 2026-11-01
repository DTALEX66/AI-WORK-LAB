# SPDX-License-Identifier: MIT
"""Read back one known real Illustrator bundle through a temporary local server."""
import hashlib
import http.client
import json
from pathlib import Path
import secrets
import sys
import threading

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from design_lab.http_service import make_server
from design_lab.service import ProjectService


def main():
    if sys.argv[1:]:raise ValueError('fixed readback accepts no arguments')
    access=secrets.token_hex(32)  # Ephemeral test authorization, never persisted or printed.
    server=make_server(ProjectService(ROOT),access)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=20)
    route=('/api/projects/e90a75cf81cf4f99bef3965d46d49cbf/bundles/'
           'bundle-native-5e8fc10585a08bf93fbe4bf070770e318d778df2d885d765ca45c2481b1f204b/'
           'versions/v-25bad7a473a74d15848ceeba8261578b/content')
    try:
        client.request('GET',route,headers={'Authorization':'Bearer '+access})
        response=client.getresponse();data=response.read();digest=hashlib.sha256(data).hexdigest()
        if response.status!=200 or digest!='c0d3cf5323274efe72ab72c733c77420fbbd8b1f2ef049040ffbbf586952ffb4':
            raise ValueError('real archive HTTP readback mismatch')
        print(json.dumps(dict(status='HTTP_NATIVE_BUNDLE_READBACK',bytes=len(data),sha256=digest)))
    finally:
        client.close();server.shutdown();server.server_close();worker.join(5)


if __name__=='__main__':main()
