# SPDX-License-Identifier: MIT
"""Scoped cancellation requests, never host-stop acknowledgements."""
from contextlib import closing
import re

from .image_assets import ImageAssetError
from .runtime import job_store as jobs
from .task_queries import TaskQueries


class TaskCommands:
    def __init__(self, service):
        self.service = service

    def cancel(self, project_id, job_id, attempt_id):
        if not isinstance(attempt_id, str) or not re.fullmatch(r'att-[0-9a-f]{32}', attempt_id):
            raise ImageAssetError(400, 'INVALID_ATTEMPT_ID')
        query = TaskQueries(self.service)
        task = query.get(project_id, job_id)['task']
        if not task['kind'].endswith('-native'):
            raise ImageAssetError(404, 'NATIVE_TASK_NOT_FOUND')
        if task['attempt']['attempt_id'] != attempt_id:
            raise ImageAssetError(409, 'ATTEMPT_CHANGED')
        try:
            with closing(jobs.connect(self.service.database, project_root=self.service.paths.project_root)) as conn:
                # The store rechecks current-attempt identity inside its write
                # transaction; a newer retry must not receive this request.
                jobs.request_cancel(conn, attempt_id)
        except jobs.AttemptError:
            raise ImageAssetError(409, 'CANCEL_NOT_ELIGIBLE') from None
        return query.get(project_id, job_id)
