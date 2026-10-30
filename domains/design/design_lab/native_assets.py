# SPDX-License-Identifier: MIT
"""Read-only native asset metadata and explicit bounded hash verification.

No filesystem paths, source jobs, approvals or native document bytes are exposed.
Registry metadata is not fresh file verification or human acceptance.
"""
from contextlib import closing
import hashlib
import re
import sqlite3

from .image_assets import ImageAssetError


class NativeAssets:
    def __init__(self,service):
        self.service=service;self.paths=service.paths

    def _rows(self,project_id,asset_id=None,after=''):
        if self.service.get_project(project_id) is None:raise ImageAssetError(404,'PROJECT_NOT_FOUND')
        path=self.paths.database_path(self.service.database)
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as conn:
            conn.row_factory=sqlite3.Row
            return conn.execute('''SELECT a.asset_id,a.asset_kind,v.version_id,v.version_no,
 f.path,f.sha256,f.byte_size FROM asset a
 JOIN asset_version v ON v.asset_id=a.asset_id JOIN artifact f ON f.version_id=v.version_id
 WHERE a.project_id=? AND a.asset_kind IN ('psd','ai') AND v.state='ACTIVE'
 AND a.asset_id LIKE 'native-%' AND (? IS NULL OR a.asset_id=?) AND a.asset_id>?
 AND v.version_no=(SELECT MAX(b.version_no) FROM asset_version b WHERE b.asset_id=a.asset_id AND b.state='ACTIVE')
 AND f.artifact_id=(SELECT g.artifact_id FROM artifact g WHERE g.version_id=v.version_id
   ORDER BY CASE g.role WHEN 'deliverable' THEN 0 ELSE 1 END, g.path LIMIT 1)
 ORDER BY a.asset_id LIMIT 101''',(project_id,asset_id,asset_id,after)).fetchall()

    @staticmethod
    def _metadata(row):
        return dict(id=row['asset_id'],kind=row['asset_kind'],version_id=row['version_id'],version_no=row['version_no'],
            byte_size=row['byte_size'],sha256='sha256:'+row['sha256'].removeprefix('sha256:'),
            rights='NOT_REVIEWED',verification='METADATA_ONLY')

    def list(self,project_id,after=''):
        rows=self._rows(project_id,after=after)
        return dict(assets=[self._metadata(row) for row in rows[:100]],
                    next_cursor=rows[99]['asset_id'] if len(rows)>100 else None)

    def verify(self,project_id,asset_id):
        if not re.fullmatch(r'native-[0-9a-f]{64}',asset_id):raise ImageAssetError(404,'NATIVE_ASSET_NOT_FOUND')
        rows=self._rows(project_id,asset_id)
        if len(rows)!=1:raise ImageAssetError(404,'NATIVE_ASSET_NOT_FOUND')
        row=rows[0]
        try:
            path=self.paths.checked_path(row['path']);owner=self.paths.category_dir('projects',project_id)
            if not path.is_relative_to(owner):raise ValueError('wrong owner')
            before=path.stat()
            if not path.is_file() or before.st_nlink!=1 or before.st_size!=row['byte_size'] or not 0<before.st_size<=256*1024*1024:raise ValueError('invalid size/link')
            digest=hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
            after=path.stat()
            if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):raise ValueError('changed file')
            if digest.hexdigest()!=row['sha256'].removeprefix('sha256:'):raise ValueError('hash mismatch')
        except (ValueError,OSError):raise ImageAssetError(409,'NATIVE_ARTIFACT_UNVERIFIED') from None
        return {'asset':dict(self._metadata(row),verification='HASH_VERIFIED')}


class Bundles:
    """Read-only list of a project's design bundles -- i.e. its deliveries.

    The predicate here was MEASURED, not assumed. My first version filtered on
    asset_kind='design-bundle' and the tests written first rejected it outright:
      * the asset table has CHECK (asset_kind IN ('raster','vector','text','audio','video',
        'blend','psd','ai','doc','other')) -- 'design-bundle' is NOT a legal asset_kind;
      * native_bundles.py:73 actually registers the bundle with asset_kind='other' and
        asset_id='bundle-'+<native asset id>;
      * the 'design-bundle' string in that module is a return/statement label, not a column;
      * native_delivery.py:43 reads a single delivery back via asset_kind='other' AND a
        specific version_id -- that is a single-resource lookup, not a list.
    So a query on 'design-bundle' would have matched nothing forever while looking correct.
    This class exists because no route can answer "what did I deliver?": /assets is
    raster-only by construction, and /bundles/<id>/versions/<v> is a single resource.
    """

    def __init__(self,service):
        self.service=service;self.paths=service.paths

    def list(self,project_id):
        if self.service.get_project(project_id) is None:raise ImageAssetError(404,'PROJECT_NOT_FOUND')
        path=self.paths.database_path(self.service.database)
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as conn:
            conn.row_factory=sqlite3.Row
            rows=conn.execute('''SELECT a.asset_id,a.asset_kind,v.version_id,v.version_no,
 f.sha256,f.byte_size FROM asset a
 JOIN asset_version v ON v.asset_id=a.asset_id JOIN artifact f ON f.version_id=v.version_id
 WHERE a.project_id=? AND a.asset_kind='other' AND a.asset_id LIKE 'bundle-%'
 AND v.state='ACTIVE'
 AND v.version_no=(SELECT MAX(b.version_no) FROM asset_version b
                   WHERE b.asset_id=a.asset_id AND b.state='ACTIVE')
 AND f.artifact_id=(SELECT g.artifact_id FROM artifact g WHERE g.version_id=v.version_id
   ORDER BY CASE g.role WHEN 'deliverable' THEN 0 ELSE 1 END, g.path LIMIT 1)
 ORDER BY a.asset_id LIMIT 101''',(project_id,)).fetchall()
        return {'bundles':[dict(id=r['asset_id'],kind='design-bundle',version_id=r['version_id'],
            version_no=r['version_no'],byte_size=r['byte_size'],
            sha256='sha256:'+r['sha256'].removeprefix('sha256:'),
            rights='NOT_REVIEWED',verification='METADATA_ONLY') for r in rows[:100]]}
