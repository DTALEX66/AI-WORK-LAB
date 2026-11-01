// WUI-12 · settings, privacy and the collection lifecycle, as far as a read-only projection may go.
//
// The appearance block is the only place on this page with controls, and that is deliberate: theme,
// layout and palette are facts about THIS view that already travel in the address (?theme= / ?layout= /
// ?palette=), so a control here changes nothing in the world outside the window. Everything about
// collection, retention and storage is rendered as a named gap with the producer that owns the answer —
// a settings switch that stopped collection from inside Observer would be a write affordance wearing a
// gear icon, which `apps/observer/AGENTS.md` forbids outright.
import * as React from 'react'
import { PageHeader } from '@/components/ui/page-header'
import { Card, CardHeader, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dim } from '@/views/RecordInspector'
import { APPEARANCE_ROWS, COLLECTION_GAPS, LIFECYCLE_ACTIONS, READ_ONLY_PRIVACY } from '@/lib/collectionLifecycle'
import { CollectorDeliverySummary } from '@/components/ui/collector-delivery'
import { PALETTE_LABELS, DEFAULT_PALETTE_ID, type PaletteId } from '@/theme/tokens'
import type { SnapshotV3 } from '@/types'
import type { ThemeMode, LayoutMode } from '@/lib/api'

export interface SettingsPrivacyViewProps {
  snap: SnapshotV3 | null
  theme?: ThemeMode
  layout?: LayoutMode
  palette?: PaletteId
  onTheme?: (next: ThemeMode) => void
  onLayout?: (next: LayoutMode) => void
  onPalette?: (next: PaletteId) => void
}

const APPEARANCE_VALUE: Record<'theme' | 'palette' | 'layout', (props: SettingsPrivacyViewProps) => string> = {
  theme: (p) => (p.theme === 'light' ? '浅色' : p.theme === 'dark' ? '深色' : '未由壳传入（按地址解析）'),
  layout: (p) => (p.layout === 'compact' ? '紧凑 HUD（440×680 桌面浮窗）'
    : p.layout === 'full' ? '主窗（默认 1280×820，下限 900×600）' : '未由壳传入（按地址解析）'),
  palette: (p) => (p.palette ? PALETTE_LABELS[p.palette] : PALETTE_LABELS[DEFAULT_PALETTE_ID]),
}

export function SettingsPrivacyView(props: SettingsPrivacyViewProps) {
  const { theme, layout, palette, onTheme, onLayout, onPalette } = props
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="设置与隐私"
        description="低频页。这里只放与本页有关、且真的能被本页改变的东西：外观三选。采集、保留、存储与诊断范围不在快照里，就按缺口列出并指明属主，不伪装成可配置项。"
      />

      <Card>
        <CardHeader>
          <span>外观（状态只走地址）</span>
          <span className="text-[12px] text-muted">不写 web storage</span>
        </CardHeader>
        <CardContent>
          <div className="list">
            {APPEARANCE_ROWS.map((row) => (
              <div key={row.key} className="list-item" data-appearance={row.key}>
                <div className="min-w-0">
                  <div className="text-[12px] font-semibold text-ink">{row.label}</div>
                  <div className="text-[12px] text-muted">{row.travels}</div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge variant="info">{APPEARANCE_VALUE[row.key](props)}</Badge>
                  {row.key === 'theme' && onTheme && (
                    <button
                      type="button" className="ghost-btn" data-setting="theme"
                      onClick={() => onTheme(theme === 'dark' ? 'light' : 'dark')}
                    >
                      {theme === 'dark' ? '切到浅色' : '切到深色'}
                    </button>
                  )}
                  {row.key === 'layout' && onLayout && (
                    <button
                      type="button" className="ghost-btn" data-setting="layout"
                      onClick={() => onLayout(layout === 'compact' ? 'full' : 'compact')}
                    >
                      {layout === 'compact' ? '回到主窗' : '切到紧凑 HUD'}
                    </button>
                  )}
                  {row.key === 'palette' && onPalette && (
                    <button
                      type="button" className="ghost-btn" data-setting="palette"
                      onClick={() => onPalette(palette === DEFAULT_PALETTE_ID ? 'master' : DEFAULT_PALETTE_ID)}
                    >
                      {palette === DEFAULT_PALETTE_ID ? '改用母版建议配色' : '切回现行配色'}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 text-[12px] text-muted">
            减少动态效果跟随系统 `prefers-reduced-motion`，不是本页的开关：系统设了什么，本页就照什么渲染。
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <span>采集、白名单、保留与存储</span>
          <span className="tag warn">快照不投影</span>
        </CardHeader>
        <CardContent>
          <div className="list">
            {COLLECTION_GAPS.map((gap) => (
              <Dim key={gap.key} label={gap.question} value={null} hint={gap.reason} />
            ))}
          </div>
          <div className="mt-3 text-[12px] text-muted">
            以上没有一项渲染成开关或滑块：把仓库的意图显示成运行态，比留白更糟。
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <span>每个采集器交出了多少行、拒绝了多少行</span>
          <span className="text-[12px] text-muted">读自快照 `collectors`（ERR-256 的持久计数）</span>
        </CardHeader>
        <CardContent>
          <CollectorDeliverySummary collectors={props.snap?.collectors} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <span>四种「停止」是四件事</span>
          <span className="text-[12px] text-muted">属主各归各</span>
        </CardHeader>
        <CardContent>
          <div className="list">
            {LIFECYCLE_ACTIONS.map((action) => (
              <div key={action.key} className="list-item flex-col items-stretch gap-1" data-lifecycle={action.key}>
                <div className="text-[12px] font-semibold text-ink">{action.label}</div>
                <div className="text-[12px] text-muted">发生什么：{action.effect}</div>
                <div className="text-[12px] text-muted">属主：{action.owner}</div>
                <div className="text-[12px] text-warning">本页：{action.here}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><span>本页的只读与隐私边界</span></CardHeader>
        <CardContent>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {READ_ONLY_PRIVACY.map((line) => (
              <li key={line} className="text-[12px] text-muted">· {line}</li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}
