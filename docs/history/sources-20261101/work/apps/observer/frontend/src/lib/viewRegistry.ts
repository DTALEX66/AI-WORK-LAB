// U04: typed frontend view registry. One source of truth for the navigation
// lanes. Replaces the array-index coupling in App.tsx (views[view]) where the
// Sidebar had 8 items but the views array had 10, making Delivery/Trust/
// Settings unreachable. Every view is now reachable by a stable id.
//
// Icons come from lucide-react; the component is a lazy-free static reference
// (all views are small and already bundled). Adding a view = add one row here.
import type { ComponentType } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  LayoutDashboard, Bot, PlayCircle, Cpu, Brain, Wrench, Activity,
  Package, FolderGit2, ShieldCheck, Settings,
  ScrollText, History, CheckCircle2, Plug, PackageCheck, SquareKanban,
  Workflow, Network, GitBranch, FileSearch, FolderOpen,
  // WUI-05/06/07/09 destination lanes
  Layers, BarChart3, Boxes, SlidersHorizontal,
  // WUI-21: the three isolated-trial surfaces
  FlaskConical, ShieldAlert, RotateCcw,
} from 'lucide-react'
import {
  AgentsView, ExecutionsView, ModelsView, MemoryView, ToolsView,
  MonitoringView, DeliveryView, TrustView, SettingsView, ProjectsView,
} from '@/views/Views'
import { SoftwareView } from '@/views/SoftwareView'
// WUI-02 (20261009): the object-detail surface. One address (?projectId=) resolves one project
// identity, and the collaboration summary lives here rather than in its own lane, per WUI-01.
import { ProjectDetailView } from '@/views/ProjectDetailView'
// WUI-05/06/07/09: the four remaining destination pages. Each composes the legacy lane's real projection
// instead of replacing it, so the legacy ids below stay reachable and keep their own words.
import { UsageCacheView } from '@/views/UsageCacheView'
import { SoftwareEnvironmentView } from '@/views/SoftwareEnvironmentView'
import { CapabilityAssetsView } from '@/views/CapabilityAssetsView'
import { RuleAdaptationView } from '@/views/RuleAdaptationView'
// WUI-12: the privacy / collection-lifecycle surface. Separate from the legacy 设置 lane on purpose:
// that one is the existing settings view, this one answers what is collected, retained and stoppable.
import { SettingsPrivacyView } from '@/views/SettingsPrivacyView'
// D3 (2026-09-26 stage D): primary Work lane — the first read-only visible
// closed loop (entry -> project -> task/execution -> state/failure ->
// Context/Evidence -> next step) with a right-side Inspector.
import { WorkView } from '@/views/WorkView'
// REQ-RANGE-20261007: the evidence slice lane — three columns per artifact (identity / slice / verdict),
// reading the sidecar's typed `worklab/evidence-range-result/v1` body instead of an opaque reference.
import { EvidenceView } from '@/views/EvidenceView'
// WUI-21: one component, three lanes — 方案 / 失败 / 读回.
import { TrialPlanView, TrialFailureView, TrialReadbackView } from '@/views/IsolatedTrialView'
// UI_VIEWS (20260921): five L7-aligned governance lanes (honest projections).
import { RulesPolicyView } from '@/views/RulesPolicyView'
import { AuditTrailView } from '@/views/AuditTrailView'
import { ApprovalsView } from '@/views/ApprovalsView'
import { IntegrationsView } from '@/views/IntegrationsView'
import { TaskPacksView } from '@/views/TaskPacksView'
// L10 (2026-09-27): B10 final-deployable lanes (B07 IA page matrix) —
// Workflows / Workflow Editor / Observer / Execution Detail.
import { WorkflowsView } from '@/views/WorkflowsView'
import { WorkflowEditorView } from '@/views/WorkflowEditorView'
import { ObserverView } from '@/views/ObserverView'
import { ExecutionDetailView } from '@/views/ExecutionDetailView'

export interface ViewEntry {
  id: string
  label: string
  icon: LucideIcon
  component: ComponentType<any>
  /** taskpack lane the view satisfies */
  lane:
    | 'overview' | 'agents' | 'executions' | 'models' | 'memory' | 'tools'
    | 'monitoring' | 'delivery' | 'trust' | 'settings' | 'software'
    | 'projects'
    // D3 (2026-09-26 stage D): primary Work lane
    | 'work'
    // UI_VIEWS (20260921): L7 governance lanes
    | 'rules-policy' | 'audit' | 'approvals' | 'integrations' | 'task-packs'
    // L10 (2026-09-27): B10 final-deployable lanes
    // L10 (2026-09-27): B10 final-deployable lanes
    | 'workflows' | 'workflow-editor' | 'observer' | 'execution-detail'
    // REQ-RANGE-20261007: evidence slice lane (identity / slice / verdict)
    | 'evidence'
    // WUI-02 (20261009): object detail — one project identity, its participants, axes and collaboration summary
    | 'project-detail'
    // WUI-05/06/07/09 (20261009): the four destination pages, each composing the legacy lane(s) it absorbs
    | 'usage' | 'environment' | 'capabilities' | 'rules-adaptation'
    // WUI-12 (20261009): privacy and the collection lifecycle
    | 'privacy'
    // WUI-21 (20261012): isolated trial — 方案 / 失败 / 读回
    | 'trial-plan' | 'trial-failure' | 'trial-readback'
}

// TaskPack U04 lanes: Overview, Projects, Agents, Executions, Models/Usage,
// Memory, Tools/Capabilities, Monitoring/System, Delivery, Trust, Settings.
// Projects is folded into the Agents/Projects panel (AgentsView already renders
// the per-project platform cards) — documented decision, not a separate view.
export const VIEW_REGISTRY: ViewEntry[] = [
  // D3 (2026-09-26 stage D): Work is the primary read-only closed-loop lane
  // (entry -> project -> task/execution -> state/failure -> Context/Evidence
  // -> next step) with a right-side Inspector. It reuses the SAME real v3
  // snapshot projection (no second ledger, no fabricated fields).
  { id: 'work',         label: '工作',   icon: SquareKanban,  component: WorkView,         lane: 'work' },
  { id: 'agents',       label: '智能体', icon: Bot,             component: AgentsView,       lane: 'agents' },
  // P1-D §3.1 (2026-09-26): Projects promoted to a first-level entry. The
  // project-platform table was folded into AgentsView (U04); it is now a
  // dedicated read-only view reusing the SAME real snap.projects projection.
  { id: 'projects',     label: '项目',   icon: FolderGit2,     component: ProjectsView,     lane: 'projects' },
  // WUI-02: the object-detail lane. Addressed by ?projectId=, it is the one surface that answers
  // "what does the projection know about THIS project" — identity, participants, the three axes,
  // freshness, known usage and the collaboration summary. Named 项目详情 rather than 详情 because a
  // per-lane distinct heading is what tells a user the rail moved (see offlineViewIdentity contract).
  { id: 'project-detail', label: '项目详情', icon: FolderOpen, component: ProjectDetailView, lane: 'project-detail' },
  // WUI-05/06/07/09 · the four destination pages. Each one composes the legacy lane(s) whose data it
  // presents (software inside environment, tools+capability ladder inside capabilities, models inside
  // usage), so nothing already working is rewritten — the destination adds the questions, the legacy lane
  // stays the compatible entry to the same projection.
  { id: 'environment',   label: '软件环境', icon: Layers,           component: SoftwareEnvironmentView, lane: 'environment' },
  { id: 'capabilities',  label: '能力资产', icon: Boxes,            component: CapabilityAssetsView,    lane: 'capabilities' },
  { id: 'usage',         label: '用量缓存', icon: BarChart3,        component: UsageCacheView,          lane: 'usage' },
  { id: 'rules-adaptation', label: '规则适配', icon: SlidersHorizontal, component: RuleAdaptationView,   lane: 'rules-adaptation' },
  // WUI-12: privacy and the collection lifecycle. The legacy 设置 lane stays next to it because deleting
  // a working view is not how a destination is added.
  { id: 'privacy',      label: '隐私与采集', icon: ShieldCheck,   component: SettingsPrivacyView,   lane: 'privacy' },
  { id: 'executions',   label: '执行',   icon: PlayCircle,      component: ExecutionsView,   lane: 'executions' },
  // WUI-05..09 put the destination words on the NEW destination lanes; these four legacy lanes keep their
  // own original words, because a compatibility entry that renames itself to look like the destination is
  // how two entries end up claiming to be the same page.
  { id: 'models',       label: '模型',   icon: Cpu,             component: ModelsView,       lane: 'models' },
  { id: 'memory',       label: '记忆',   icon: Brain,           component: MemoryView,       lane: 'memory' },
  { id: 'tools',        label: '工具',   icon: Wrench,          component: ToolsView,        lane: 'tools' },
  { id: 'monitoring',   label: '监控',   icon: Activity,        component: MonitoringView,   lane: 'monitoring' },
  { id: 'delivery',     label: '交付',   icon: Package,         component: DeliveryView,     lane: 'delivery' },
  { id: 'trust',        label: '可信',   icon: ShieldCheck,     component: TrustView,        lane: 'trust' },
  // S31/32: read-only software location panel (location drift / duplicate install
  // surfaced instead of a false "Healthy").
  { id: 'software',     label: '软件',   icon: LayoutDashboard, component: SoftwareView,     lane: 'software' },
  { id: 'settings',     label: '设置',   icon: Settings,        component: SettingsView,   lane: 'settings' },
  // UI_VIEWS (20260921): L7-aligned governance lanes (honest projections,
  // read-only; each view renders an EmptyState/UnknownState when its data
  // source is absent from the snapshot).
  { id: 'rules-policy', label: '规则策略', icon: ScrollText,    component: RulesPolicyView, lane: 'rules-policy' },
  { id: 'audit',        label: '审计追踪', icon: History,       component: AuditTrailView,  lane: 'audit' },
  { id: 'approvals',    label: '审批中心', icon: CheckCircle2,  component: ApprovalsView,   lane: 'approvals' },
  { id: 'integrations', label: '集成/MCP', icon: Plug,          component: IntegrationsView, lane: 'integrations' },
  { id: 'task-packs',   label: '任务包',   icon: PackageCheck,  component: TaskPacksView,   lane: 'task-packs' },
  // L10 (2026-09-27): B10 final-deployable lanes (B07 page matrix) —
  // Workflows / interactive Workflow Editor / read-only Observer /
  // Execution Detail.
  { id: 'workflows',         label: '工作流',   icon: Workflow,    component: WorkflowsView,         lane: 'workflows' },
  { id: 'workflow-editor',   label: '编辑器',   icon: GitBranch,   component: WorkflowEditorView,    lane: 'workflow-editor' },
  { id: 'observer',         label: '观察者',   icon: Network,     component: ObserverView,          lane: 'observer' },
  { id: 'execution-detail',  label: '执行详情', icon: PlayCircle,  component: ExecutionDetailView,   lane: 'execution-detail' },
  // REQ-RANGE-20261007: the evidence lane rides the same registry so the per-lane truth sweeps cover it
  // the moment it exists — a lane that only its own test file can reach is the lane that regresses.
  { id: 'evidence',          label: '证据区间', icon: FileSearch,  component: EvidenceView,          lane: 'evidence' },
  // WUI-21: the isolated-trial surfaces — 方案 / 失败 / 读回 — registered as three lanes over ONE
  // component rather than three files, so a future change to the read model cannot land in two of them.
  { id: 'trial-plan',        label: '试用方案', icon: FlaskConical, component: TrialPlanView,     lane: 'trial-plan' },
  { id: 'trial-failure',     label: '试用失败', icon: ShieldAlert,  component: TrialFailureView,  lane: 'trial-failure' },
  { id: 'trial-readback',    label: '试用读回', icon: RotateCcw,    component: TrialReadbackView, lane: 'trial-readback' },
]

export const VIEW_BY_ID: Record<string, ViewEntry> = Object.fromEntries(
  VIEW_REGISTRY.map((v) => [v.id, v])
)

// Overview is rendered inline in App.tsx (KPI cards + agents + cost) and is the
// default landing view, so it is not a registry entry with its own component —
// it is a synthetic first lane.
export const OVERVIEW_ID = 'overview'

// N-1: the label lived in App.tsx, Sidebar.tsx and OverviewView.tsx as three
// separate string literals, so the nav could say 总览 while the page header said
// anything else. Overview has no registry entry, so it needs its own constant.
//
// WUI-01 (20261009): the lane is now the 项目监控 home — the owner's route table maps `overview` into
// 项目监控 and forbids a second home, so the id stays and the word changes. Nothing outside this
// constant may spell it: the desktop component contract fails on a second source.
export const OVERVIEW_LABEL = '项目监控'

// Same reasoning as N-1 above, one axis over: the rail needs a glyph for this lane and the lane has no
// registry row to declare it, so the icon lives beside the label rather than being minted inside the
// component (a glyph chosen in a component is a second source that can drift from the registry's set).
// It borrows 监控's `Activity` instead of taking a 31st glyph, which is the convention the registry already
// uses for paired surfaces (`executions` and `execution-detail` share `PlayCircle`; `privacy` and `trust`
// share `ShieldCheck`).
export const OVERVIEW_ICON = Activity
