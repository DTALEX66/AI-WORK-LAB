// S31/S32 (taskpack 20260919) · L10b (2026-09-27): read-only software
// installation-identity panel.
//
// The Observer projects the software-installation-identity contract (U17/P0-07)
// already resolved by the sidecar/DHS adapter. It NEVER acts on it (no second
// Update Authority, no relocation, no delete). When DSH has drifted to C: or a
// duplicate install exists, this panel shows LOCATION_DRIFT / DUAL_INSTALLATION
// — NOT "Healthy".
//
// L10b: the B10 `.panel` + `.list` / `.list-item` structure (each software
// entry is a `.panel` block with a `.list` of detail rows) and `.tag` pills.
import { Card, CardHeader, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { SoftwareIdentity, SoftwareLocationStatus } from '@/types'
import { fmtTimestamp } from '@/lib/api'

const STATUS_LABEL: Record<SoftwareLocationStatus, string> = {
  NOT_INSTALLED: '未安装',
  SINGLE_VERIFIED: '单一·已验证',
  SINGLE_UNVERIFIED: '单一·未验证',
  LOCATION_DRIFT: '位置漂移',
  DUAL_INSTALLATION: '双安装',
  MISSING_EXPECTED_INSTALL: '预期安装缺失',
  RELOCATION_REQUESTED: '请求迁移',
  OS_MANAGED: '系统托管',
  UNKNOWN: '未知',
}

function statusVariant(s: SoftwareLocationStatus): 'success' | 'warning' | 'error' | 'muted' {
  switch (s) {
    case 'SINGLE_VERIFIED': return 'success'
    case 'SINGLE_UNVERIFIED':
    case 'OS_MANAGED':
    case 'RELOCATION_REQUESTED':
    case 'NOT_INSTALLED':
      return 'muted'
    case 'LOCATION_DRIFT':
    case 'DUAL_INSTALLATION':
    case 'MISSING_EXPECTED_INSTALL':
      return 'error'
    default:
      return 'muted'
  }
}

function Row({ k, v, mono = false }: { k: string; v: React.ReactNode; mono?: boolean }) {
  return (
    <div className="list-item">
      <span className="text-[12px] text-muted">{k}</span>
      <span className={'ml-3 min-w-0 truncate text-right text-[12px] text-ink' + (mono ? ' font-mono' : '')}>{v}</span>
    </div>
  )
}

export function SoftwareView({ snap }: { snap: any }) {
  const software: SoftwareIdentity[] = Array.isArray(snap?.software) ? snap.software : []
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <span>软件安装身份（只读投影）</span>
          <span className="text-[12px] text-muted">
            {software.length ? software.length + ' 项 · 真实' : '无数据（UNKNOWN）'}
          </span>
        </CardHeader>
        <CardContent>
          {software.length === 0 ? (
            <div className="empty py-10">
              <div className="icon" aria-hidden="true">▤</div>
              <p className="m-0 text-sm font-semibold text-ink">无软件身份投影</p>
              <p className="mx-auto mt-1 max-w-md text-xs">后端未提供 · 保持 UNKNOWN，不伪造 Healthy</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {software.map((s) => (
                <div key={s.softwareId} className="panel">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <strong className="text-xs font-semibold text-ink">{s.displayName || s.softwareId}</strong>
                    <Badge variant={statusVariant(s.locationStatus)}>
                      {STATUS_LABEL[s.locationStatus] || s.locationStatus}
                    </Badge>
                  </div>
                  <div className="list">
                    <Row k="安装位置" v={s.installRoot || 'UNKNOWN'} mono />
                    <Row k="可执行" v={s.executableRealpath || 'UNKNOWN'} mono />
                    <Row k="发现版本" v={s.discoveredVersion || 'UNKNOWN'} mono />
                    <Row k="渠道" v={s.releaseChannel || 'UNKNOWN'} />
                    <Row k="更新可用" v={s.updateAvailable == null ? 'UNKNOWN' : s.updateAvailable ? '是' : '否'} />
                    <Row k="双安装" v={s.duplicateInstallation ? '是' : '否'} />
                    <Row k="预期位置" v={s.expectedLocation || '—'} mono />
                    <Row k="观测位置" v={s.observedLocation || '—'} mono />
                    <Row k="最后核验" v={fmtTimestamp(s.lastVerified)} />
                    <Row k="发现源" v={s.discoverySource || '—'} />
                  </div>
                  {s.locationStatus === 'LOCATION_DRIFT' && s.expectedLocation && s.observedLocation && (
                    <div className="mt-2 text-[12px] text-error">
                      漂移：预期 <span className="font-mono">{s.expectedLocation}</span> · 观测
                      <span className="font-mono"> {s.observedLocation}</span> — 需明确 RELOCATION 授权，
                      Observer 不自动迁移
                    </div>
                  )}
                  {s.locationStatus === 'DUAL_INSTALLATION' && (
                    <div className="mt-2 text-[12px] text-error">
                      检测到多实例 — 先确定 canonical 实例；Observer 不自动删除任何实例
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><span>原则</span></CardHeader>
        <CardContent className="text-xs text-muted">
          软件位置真值来自后端安装身份契约（U17/P0-07）。Observer 仅投影，绝不构成第二
          Update Authority；位置漂移/双安装如实呈现，不伪装 Healthy。
        </CardContent>
      </Card>
    </div>
  )
}
