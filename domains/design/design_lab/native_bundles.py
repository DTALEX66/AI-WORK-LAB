# SPDX-License-Identifier: MIT
"""Internal verified native bundle export, preserving the primary-asset API.

Every delivery published here also carries a DeliveryReceipt V2: it is built from the
archive manifest only after ``verify_bundle`` has re-read every member, validated
against ``design-lab/schemas/interop-delivery-receipt-v2.schema.json`` inside this
product path, and persisted next to the version it describes. A receipt that cannot be
built honestly stops the export instead of shipping a document that overclaims.
"""
from contextlib import closing
import json
from pathlib import Path
import re

from .interop import InteropError, delivery_receipt
from .runtime import asset_store as assets, job_store as jobs
from .runtime.bundle_store import publish_bundle, verify_bundle
from .runtime.native_recovery_lock import recovery_lock


def _ensure_receipt_table(conn):
    """Own the receipt ledger here: it belongs to delivery export, not to the host."""
    conn.execute('CREATE TABLE IF NOT EXISTS delivery_receipt_v1 ('
        'version_id TEXT PRIMARY KEY REFERENCES asset_version(version_id),'
        ' project_id TEXT NOT NULL REFERENCES project(project_id),'
        ' asset_id TEXT NOT NULL REFERENCES asset(asset_id),'
        ' job_id TEXT NOT NULL, receipt_id TEXT NOT NULL UNIQUE,'
        ' receipt_sha256 TEXT NOT NULL UNIQUE, receipt_json TEXT NOT NULL, stored_at TEXT NOT NULL)')


def _rollback_of(source):
    """The restore point a bundle delivery genuinely has: the immutable version it was
    exported from. The export only appends a new asset version, so dropping that
    appended version returns the recorded state. No restore is performed here, and the
    receipt itself declares its rollback record to be a plan.
    """
    return dict(backup_ref=f"asset:{source['id']}/version:{source['version_id']}",
                procedure='remove the appended bundle version from the project asset store; the '
                          f"source native version {source['version_id']} this archive was exported "
                          'from is unmodified by the export and was hash-verified when this receipt '
                          'was written. No restore has been performed.')


def _receipt_for_version(conn, *, manifest, attempt, project_id, asset_id, version, source):
    """Build, validate, persist and return the receipt for one published version.

    Idempotent by construction: the receipt reads only persisted, immutable facts, so a
    replay rebuilds the identical document. A stored receipt that differs from the
    rebuilt one is a real integrity break and fails closed rather than being rewritten.
    """
    from .native_tasks import NativeTaskError
    created=conn.execute('SELECT created_at FROM asset_version WHERE version_id=?',(version,)).fetchone()
    if not created or not created[0]:
        raise NativeTaskError('BUNDLE_RECEIPT_UNAVAILABLE')
    try:
        receipt=delivery_receipt.receipt_for_bundle(manifest,
            job_id=attempt['job_id'], created_at=created[0], receipted_at=attempt['ended_at'],
            rollback=_rollback_of(source), bundle_bytes_verified=True)
        text=delivery_receipt.dumps(receipt)
    except (InteropError, KeyError, TypeError, ValueError) as exc:
        raise NativeTaskError('BUNDLE_RECEIPT_UNVERIFIABLE') from exc
    _ensure_receipt_table(conn)
    stored=conn.execute('SELECT receipt_json,receipt_id,receipt_sha256 FROM delivery_receipt_v1 '
                        'WHERE version_id=?',(version,)).fetchone()
    if stored:
        if tuple(stored)!=(text,receipt['receipt_id'],receipt['receipt_sha256']):
            raise NativeTaskError('BUNDLE_RECEIPT_CONFLICT')
        return receipt
    with assets._transaction(conn):
        conn.execute('INSERT INTO delivery_receipt_v1 VALUES (?,?,?,?,?,?,?,?)',
            (version,project_id,asset_id,receipt['job_id'],receipt['receipt_id'],
             receipt['receipt_sha256'],text,assets._now()))
    return receipt


def _requested_fonts(job):
    """Describe sealed job intent, never infer host font or redistribution rights."""
    fonts={}
    pending=list(job['layers'])
    while pending:
        item=pending.pop()
        if item.get('kind')=='text':
            name=item['font'];identity=item['id']
            if not isinstance(name,str) or not name.strip() or not isinstance(identity,str):
                raise ValueError('invalid requested font binding')
            fonts.setdefault(name,set()).add(identity)
        for child_key in ('items','contours','children'):
            pending.extend(item.get(child_key,[]))
    return [dict(postscript_name=name,object_ids=sorted(ids)) for name,ids in sorted(fonts.items())]


def export_bundle(tasks, attempt_id, authorization):
    from .native_tasks import NativeTaskError
    if (not isinstance(authorization,dict) or set(authorization)!={'actor','scope','receipt'}
        or authorization['scope']!='project-native-test'
        or any(not isinstance(v,str) or not v.strip() or len(v)>2000 for v in authorization.values())):
        raise NativeTaskError('BUNDLE_AUTHORIZATION_REQUIRED')
    try:
        with recovery_lock(tasks.paths,attempt_id), closing(tasks._connect()) as conn:
            attempt,_=jobs._current(conn,attempt_id)
            row=conn.execute('SELECT host,project_id,request_json,receipt_json FROM native_execution_v1 WHERE attempt_id=?',
                             (attempt_id,)).fetchone()
            if attempt['state']!='RECEIPTED' or not row or not row[3]:
                raise NativeTaskError('BUNDLE_NATIVE_NOT_VERIFIED')
            host,project_id,request_raw,receipt_raw=row
            result=tasks._existing(conn,attempt,project_id)
            request=json.loads(request_raw);receipt=json.loads(receipt_raw);job=request['job']
            root=tasks.paths.checked_path(job['runRoot'])
            raw_outputs=({'psd':root/job['outputName'],'png':root/job['previewName']}
                         if host=='photoshop' else job['targets'])
            outputs={kind:tasks._inside(path,root) for kind,path in raw_outputs.items()}
            tasks._verify_receipt(receipt,job,request,outputs)
            primary='psd' if host=='photoshop' else 'ai'
            names={primary:'native.'+primary,'png':'preview.png','svg':'preview.svg'}
            files={names[kind]:dict(path=str(path),sha256=receipt['artifacts'][kind]['sha256'],
                                   role='primary' if kind==primary else 'preview') for kind,path in outputs.items()}
            input_names={}
            for index,(source,digest) in enumerate(sorted(request['inputs'].items())):
                suffix=Path(source).suffix.lower()
                if not re.fullmatch(r'\.[a-z0-9]{1,12}',suffix):suffix='.bin'
                name=f'inputs/{index:04d}{suffix}'
                input_names[source]=name
                files[name]=dict(path=str(tasks._inside(source,root)),sha256=digest['sha256'],role='input')
            metadata=dict(native_attempt_id=attempt_id,source_asset_id=result['asset']['id'],host=host,
                          host_version=receipt.get('host_version','UNKNOWN'),job_sha256=receipt['job_sha256'],
                          rights='NOT_REVIEWED',quality='NOT_REVIEWED',link_relocation='NOT_VERIFIED',
                          font_inventory='REQUESTED_ONLY',requested_fonts=_requested_fonts(job),
                          font_observation='NOT_COLLECTED',font_rights='NOT_REVIEWED',
                          native_receipt_binding=dict(attempt_id=attempt_id,
                              bridge_sha256=receipt['bridge_sha256'],job_sha256=receipt['job_sha256']),
                          input_assets=[dict(id=item['id'],member=input_names[str(tasks.paths.checked_path(item['path']))])
                                        for item in job['assets']])
            asset_id='bundle-'+result['asset']['id']
            store=tasks.paths.category_dir('projects',project_id,'assets')
            with closing(assets.connect(tasks.service.database,project_root=tasks.owner)) as publication:
                assets.register_asset(publication,project_id,asset_id,'other')
                resource='asset:'+asset_id
                if not assets.acquire_writer(publication,resource,attempt_id):
                    assets.takeover_writer(publication,resource,attempt_id,expected_holder=attempt_id)
                generation=assets.writer_token(publication,resource,attempt_id)
                try:
                    assets.recover_publications(publication,store_root=store,project_root=tasks.owner,
                                                asset_id=asset_id,holder_attempt_id=attempt_id,generation=generation)
                    version=publish_bundle(publication,asset_id,files,primary=names[primary],metadata=metadata,
                                           store_root=store,holder_attempt_id=attempt_id,generation=generation,project_root=tasks.owner)
                    artifact=publication.execute('SELECT path,sha256,byte_size FROM artifact WHERE version_id=?',(version,)).fetchone()
                    path=tasks._inside(artifact[0],store)
                    if assets._file_hash(path)!=artifact[1] or path.stat().st_size!=artifact[2]:
                        raise NativeTaskError('BUNDLE_PUBLISHED_BYTES_CHANGED')
                    manifest=verify_bundle(path,project_root=tasks.owner)
                    receipt=_receipt_for_version(publication,manifest=manifest,attempt=attempt,
                        project_id=project_id,asset_id=asset_id,version=version,source=result['asset'])
                    return dict(id=asset_id,version_id=version,path=str(path),sha256=artifact[1].removeprefix('sha256:'),
                                byte_size=artifact[2],kind='design-bundle',rights='NOT_REVIEWED',
                                receipt=receipt)
                finally:
                    assets.release_writer(publication,resource,attempt_id,generation=generation)
    except NativeTaskError:
        raise
    except Exception as exc:
        raise NativeTaskError('BUNDLE_EXPORT_UNVERIFIED') from exc
