# SPDX-License-Identifier: MIT
"""Verified local image imports backed by the existing attempt and asset stores."""
import base64
import binascii
from contextlib import closing
import hashlib
import io
import os
import re
import sqlite3

from .runtime import asset_store as assets, job_store as jobs
from .runtime.attempt_contract import request_hash


class ImageAssetError(ValueError):
    def __init__(self, status, code):
        self.status, self.code = status, code


def inspect_image(data):
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {'PNG', 'JPEG'} or image.width * image.height > 25_000_000:
                raise ValueError('unsupported image')
            if getattr(image, 'n_frames', 1) != 1:
                raise ValueError('animated image')
            info = {'width': image.width, 'height': image.height,
                    'media_type': {'PNG': 'image/png', 'JPEG': 'image/jpeg'}[image.format]}
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
        return info
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        raise ImageAssetError(400, 'INVALID_OR_UNSUPPORTED_IMAGE') from None


class ImageAssets:
    def __init__(self, service):
        self.service = service
        self.paths = service.paths

    def require_project(self, project_id):
        if not re.fullmatch(r'[0-9a-f]{32}', project_id) or self.service.get_project(project_id) is None:
            raise ImageAssetError(404, 'PROJECT_NOT_FOUND')

    def _read(self, project_id, asset_id=None):
        self.require_project(project_id)
        self.paths.database_path(self.service.database)
        with closing(sqlite3.connect(self.service.database.as_uri() + '?mode=ro', uri=True)) as conn:
            return conn.execute(
                "SELECT a.asset_id,v.version_id,f.path,f.sha256,f.byte_size FROM asset a "
                "JOIN asset_version v ON a.asset_id=v.asset_id JOIN artifact f ON f.version_id=v.version_id "
                "WHERE a.project_id=? AND a.asset_kind='raster' AND v.state='ACTIVE' "
                # Publishing never demotes the bytes it replaced, so 'ACTIVE' alone is the
                # whole revision history: without this the same asset listed twice, and
                # content() -- which requires exactly one row -- answered 404 for an asset
                # that exists. Same current-version rule native_assets and jury_store use.
                "AND v.version_no=(SELECT MAX(b.version_no) FROM asset_version b "
                "WHERE b.asset_id=v.asset_id AND b.state='ACTIVE') "
                # A version may register several artifacts, and the join would emit one row
                # per artifact -- which breaks the same one-row promise twice over: the
                # library repeats the asset, and content() reports 404 for an asset that is
                # there. Prefer the deliverable, then name; exactly one row per asset.
                "AND f.artifact_id=(SELECT g.artifact_id FROM artifact g "
                "WHERE g.version_id=v.version_id ORDER BY "
                "CASE g.role WHEN 'deliverable' THEN 0 ELSE 1 END, g.path LIMIT 1) "
                "AND (? IS NULL OR a.asset_id=?) ORDER BY a.created_at,a.asset_id",
                (project_id, asset_id, asset_id)).fetchall()

    def _verified(self, project_id, row):
        path = self.paths.checked_path(row[2])
        root = self.paths.category_dir('projects', project_id)
        if not path.is_relative_to(root):
            raise ImageAssetError(409, 'ARTIFACT_PATH_MISMATCH')
        if path.stat().st_size > 32 * 1024 * 1024:
            raise ImageAssetError(409, 'ARTIFACT_SIZE_MISMATCH')
        data = path.read_bytes()
        digest = 'sha256:' + hashlib.sha256(data).hexdigest()
        if digest != row[3] or len(data) != row[4]:
            raise ImageAssetError(409, 'ARTIFACT_HASH_MISMATCH')
        info = inspect_image(data)
        return {'id': row[0], 'version_id': row[1], 'sha256': digest,
                'byte_size': len(data), 'rights': 'NOT_REVIEWED', **info}, data

    def list(self, project_id):
        return [self._verified(project_id, row)[0] for row in self._read(project_id)]

    def content(self, project_id, asset_id):
        rows = self._read(project_id, asset_id)
        if len(rows) != 1:
            raise ImageAssetError(404, 'ASSET_NOT_FOUND')
        record, data = self._verified(project_id, rows[0])
        return {'asset': record, 'content_base64': base64.b64encode(data).decode('ascii')}

    def import_image(self, project_id, content_base64, idempotency_key):
        self.require_project(project_id)
        if not isinstance(idempotency_key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', idempotency_key):
            raise ImageAssetError(400, 'INVALID_IMPORT_KEY')
        if not isinstance(content_base64, str) or len(content_base64) > 45_000_000:
            raise ImageAssetError(413, 'IMAGE_TOO_LARGE')
        try:
            data = base64.b64decode(content_base64, validate=True)
        except (ValueError, binascii.Error):
            raise ImageAssetError(400, 'INVALID_BASE64') from None
        if not data or len(data) > 32 * 1024 * 1024:
            raise ImageAssetError(400, 'INVALID_IMAGE_SIZE')
        info = inspect_image(data)
        digest = 'sha256:' + hashlib.sha256(data).hexdigest()
        identity = hashlib.sha256((project_id + ':' + idempotency_key).encode()).hexdigest()
        op, job, asset_id = 'import-' + identity, 'job-' + identity, 'img-' + identity
        owner = self.paths.project_root
        with closing(jobs.connect(self.service.database, project_root=owner)) as conn:
            try:
                attempt = jobs.begin_attempt(conn, job, operation_id=op, idempotency_scope='image-import:' + project_id,
                                             idempotency_key=idempotency_key,
                                             request_hash=request_hash({'project': project_id, 'sha256': digest}))
            except jobs.AttemptError:
                raise ImageAssetError(409, 'IMPORT_IDEMPOTENCY_CONFLICT') from None
            if attempt['state'] == 'RECEIPTED':
                return {'asset': self.content(project_id, asset_id)['asset'], 'attempt': attempt}
            if attempt['state'] != 'PENDING':
                raise ImageAssetError(409, 'IMPORT_REQUIRES_RECONCILIATION')
            attempt = jobs.transition(conn, attempt['attempt_id'], 'RUNNING')
            aid = attempt['attempt_id']
            try:
                source = self.paths.category_dir('runtime', 'image-imports', aid) / 'input'
                self.paths.checked_path(source)
                source.parent.mkdir(parents=True, exist_ok=True)
                with source.open('xb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                with closing(assets.connect(self.service.database, project_root=owner)) as asset_conn:
                    assets.register_asset(asset_conn, project_id, asset_id, 'raster')
                    resource = 'asset:' + asset_id
                    if not assets.acquire_writer(asset_conn, resource, aid):
                        raise ImageAssetError(409, 'ASSET_WRITER_BUSY')
                    generation = assets.writer_token(asset_conn, resource, aid)
                    try:
                        assets.publish_version(asset_conn, asset_id, source,
                                               store_root=self.paths.category_dir('projects', project_id, 'assets'),
                                               artifact_name='reference.png' if info['media_type'] == 'image/png' else 'reference.jpg',
                                               expected_sha256=digest, holder_attempt_id=aid,
                                               generation=generation, project_root=owner)
                    finally:
                        assets.release_writer(asset_conn, resource, aid, generation=generation)
                record = self.content(project_id, asset_id)['asset']
                attempt = jobs.transition(conn, aid, 'RECEIPTED', evidence={
                    'operation_id': op, 'attempt_id': aid, 'artifact_sha256': digest,
                    'readback_sha256': record['sha256'], 'kind': 'local-image-import',
                    'rights': 'NOT_REVIEWED'})
                return {'asset': record, 'attempt': attempt}
            except Exception:
                current = jobs.latest_attempt(conn, job)
                if current and current['state'] == 'RUNNING':
                    jobs.transition(conn, aid, 'OUTCOME_UNKNOWN', note='image import requires reconciliation')
                raise
