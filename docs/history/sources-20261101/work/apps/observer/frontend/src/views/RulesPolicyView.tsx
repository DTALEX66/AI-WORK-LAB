// UI_VIEWS (20260921) · L10b (2026-09-27): Rules & Policy lane — projects the
// governance family states (rules/skills/memory/adapters) already resolved by
// the backend, with the verbatim B10 `.panel` + `.list` / `.list-item` rows +
// `.tag` state pills.
// Honest discipline: when the snapshot carries no family detail we render the
// B10 `.empty` state, never a fabricated "all clean" KPI.
import { Card, CardContent } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/states'
import { PageHeader } from '@/components/ui/page-header'
import { StatusPill } from '@/components/ui/status'
import type { FamilyState, GovernanceFamily } from '@/types'

const FAMILY_LABEL: Record<'rules' | 'skills' | 'memory' | 'adapters', string> = {
  rules: '规则',
  skills: '技能',
  memory: '记忆',
  adapters: '适配器',
}

const FAMILY_KEYS = ['rules', 'skills', 'memory', 'adapters'] as const

function stateVariant(s: FamilyState): 'success' | 'warning' | 'muted' {
  switch (s) {
    case 'CLEAN': return 'success'
    case 'DRIFT': return 'warning'
    default: return 'muted'
  }
}

function stateLabel(s: FamilyState): string {
  switch (s) {
    case 'CLEAN': return '干净'
    case 'DRIFT': return '漂移'
    default: return '未知'
  }
}

function hasFamilyData(f: GovernanceFamily): boolean {
  return f.state !== 'UNKNOWN' || f.drift != null || f.current != null
}

export function RulesPolicyView({ snap }: { snap: any }) {
  const families = snap?.governance?.families as
    | Record<string, GovernanceFamily>
    | undefined
  const hasAny =
    !!families && FAMILY_KEYS.some((k) => hasFamilyData(families?.[k]))

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Rules & Policy / 规则与策略"
        description="治理契约四大家族（规则/技能/记忆/适配器）的真实状态投影。只读，不修改、不新增、不执行任何治理动作；缺失即 UNKNOWN，不伪造『全部干净』。"
      />
      <Card>
        <div className="mb-3.5 flex items-center justify-between gap-3">
          <h3 className="m-0">治理契约 · 家族状态（只读投影）</h3>
          <StatusPill variant={hasAny ? 'info' : 'muted'}>{hasAny ? '携带真实明细' : '无明细（UNKNOWN）'}</StatusPill>
        </div>
        <CardContent>
          {!hasAny ? (
            <EmptyState
              title="当前快照未携带治理契约明细"
              description="governance.families 未由后端投影，或全部为 UNKNOWN。Observer 保持 UNKNOWN，不伪造『全部干净』。"
            />
          ) : (
            <div className="list">
              {FAMILY_KEYS.map((key) => {
                const fam = families?.[key]
                if (!fam) return null
                return (
                  <div key={key} className="list-item">
                    <div className="min-w-0">
                      <strong className="block text-[13px] font-semibold text-ink">{FAMILY_LABEL[key]}</strong>
                      <small>
                        漂移项：
                        <span className="font-mono text-secondary-ink">
                          {fam.drift == null ? '未知' : fam.drift}
                        </span>
                      </small>
                    </div>
                    <StatusPill variant={stateVariant(fam.state)}>{stateLabel(fam.state)}</StatusPill>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <h3>原则</h3>
        <CardContent className="text-xs text-muted">
          规则 / 技能 / 记忆 / 适配器的真值来自后端治理契约（governance.families）。
          Observer 仅投影状态，不修改、不新增、不执行任何治理动作。
        </CardContent>
      </Card>
    </div>
  )
}
