# SPDX-License-Identifier: MIT
"""Run with an installed interpreter and -I; never adds a source import path."""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import uuid

from PIL import Image
import design_lab
from design_lab.service import ProjectService
from design_lab.image_assets import ImageAssets, ImageAssetError
from design_lab.native_submissions import NativeSubmissions
from design_lab.native_workers import NativeWorkers
from design_lab.task_commands import TaskCommands


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    root.mkdir(exist_ok=False)
    (root / 'AGENTS.md').write_text('# Dedicated installed smoke fixture\n', encoding='utf-8')
    os.environ['PROJECT_LOCAL_ROOT'] = str(root / '.project-local')
    assert 'site-packages' in str(Path(design_lab.__file__).resolve())
    service = ProjectService(root)
    project = service.create_project('Installed plan smoke')['id']
    image = io.BytesIO()
    Image.new('RGBA', (8, 6), (20, 30, 40, 100)).save(image, format='PNG')
    asset = ImageAssets(service).import_image(project, base64.b64encode(image.getvalue()).decode(), 'fixture')['asset']
    rir = dict(schemaVersion='design-lab/reconstruction-ir/v1', canvas=dict(width=8, height=6, colorSpace='srgb'), layers=[
        dict(id='image', name='image', type='raster', opacity=1, bounds=dict(x=0, y=0, width=8, height=6), inferred=True,
             zOrder=0, visible=True, locked=False, blendMode='normal', raster=dict(path=asset['id'],
             crop=dict(x=0, y=0, width=8, height=6), alpha=1, sourceMappings=[]))])
    results = []
    for host in ('illustrator', 'photoshop'):
        submit = NativeSubmissions(service)
        first = submit.submit(project, host, rir, {}, 'installed-' + host)['task']
        again = NativeSubmissions(ProjectService(root)).submit(project, host, rir, {}, 'installed-' + host)['task']
        assert first['attempt']['state'] == 'PENDING'
        assert first['attempt']['attempt_id'] == again['attempt']['attempt_id']
        task = TaskCommands(service).cancel(project, first['job_id'], first['attempt']['attempt_id'])['task']
        assert task['attempt']['state'] == 'CANCELLED'
        try:
            NativeWorkers(service).start(project, first['job_id'], first['attempt']['attempt_id'])
        except ImageAssetError as error:
            assert error.code == 'NATIVE_TASK_NOT_PENDING'
        else:
            raise AssertionError('cancelled task started')
        results.append(dict(host=host, attempt_id=task['attempt']['attempt_id'], state=task['attempt']['state']))
    assert not list(root.rglob('*.ai')) and not list(root.rglob('*.psd'))
    print(json.dumps(dict(status='PASS', package=str(design_lab.__file__), root=str(root), tasks=results,
                         host_execution='NOT_EXECUTED', fixture_id=uuid.uuid4().hex), ensure_ascii=False))


if __name__ == '__main__':
    main()
