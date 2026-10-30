# SPDX-License-Identifier: MIT
"""Bounded child workers for persisted native attempts; never kill shared hosts."""
import os
from pathlib import Path
import subprocess
import sys
import threading

from .image_assets import ImageAssetError
from .task_queries import TaskQueries


class NativeWorkers:
    def __init__(self,service):
        self.service=service
        self._processes={}
        self._lock=threading.Lock()

    def start(self,project_id,job_id,attempt_id):
        query=TaskQueries(self.service)
        task=query.get(project_id,job_id)['task']
        if not task['kind'].endswith('-native'):
            raise ImageAssetError(404,'NATIVE_TASK_NOT_FOUND')
        if task['attempt']['attempt_id']!=attempt_id:
            raise ImageAssetError(409,'ATTEMPT_CHANGED')
        with self._lock:
            self._processes={aid:p for aid,p in self._processes.items() if p.poll() is None}
            if attempt_id in self._processes:return dict(task=task,worker='ALREADY_RUNNING')
            if task['attempt']['state']!='PENDING':
                raise ImageAssetError(409,'NATIVE_TASK_NOT_PENDING')
            if len(self._processes)>=2:raise ImageAssetError(409,'NATIVE_WORKER_CAPACITY')
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
            env['PROJECT_LOCAL_ROOT']=str(self.service.paths.local_root)
            package=Path(__file__).resolve().parent
            command=[sys.executable,'-B','-X','utf8']
            if package.parent.name=='src' and (package.parent.parent/'pyproject.toml').is_file():
                env['PYTHONPATH']=str(package.parent)
            else:
                command.append('-I')
                env.pop('PYTHONPATH',None)
            command+=['-m','design_lab','--project',str(self.service.paths.project_root),
                      'native-worker','--attempt',attempt_id]
            process=subprocess.Popen(command,cwd=self.service.paths.project_root,env=env,
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self._processes[attempt_id]=process
            # Reap our child even if no further HTTP requests arrive. Server
            # shutdown never terminates this child or its shared Adobe host.
            threading.Thread(target=process.wait,daemon=True).start()
        return dict(task=task,worker='STARTED')
