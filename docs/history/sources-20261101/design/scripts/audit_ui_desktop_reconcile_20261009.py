#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-UI-U01 (2026-10-09) — 桌面 UI 现状/权威/路由对账，生成可审阅的映射表。

这份脚本是**对账**，不是登记：每一个结论都从仓库里真实存在的字节推出来，任何一条
对不上就非零退出，而不是生成一份"看起来完整"的报告。

读的真实来源：
  * docs/history/taskpacks/20261009-inputs/ui/specs/screen_map.json —— 包里的桌面屏
  * docs/history/taskpacks/20261009-inputs/ui/specs/design_tokens.json —— 包的颜色/排印基线
  * apps/workbench/shell.ts —— ROUTE_VIEWS（view/hash/label/entry）与 CAPABILITY_REGISTRY
  * src/design_lab/http_service.py —— 服务实际 dispatch 的路由（借用
    verify_capability_self_description 的同一个解析器，不写第二份）
  * design-lab/config/task-ledger-r3.json —— currentExecution 的任务 id 集合
  * apps/workbench/style.css —— 已落地的 --uif-* 原语取值

拒绝的写法：把"路径存在"当验收、把旧报告的数字当现状、把没接的动作说成可用、
把未落地页写成"已完成"。未落地必须有具名取代任务与原因；已落地必须能指出服务
真的 dispatch 了那条路由。

用法：  python scripts/audit_ui_desktop_reconcile_20261009.py [--check]
        --check  只比对已提交的 MD，不写文件（CI 用）
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
UI_INPUTS = REPO / 'docs/history/taskpacks/20261009-inputs/ui/specs'
SHELL_TS = REPO / 'apps/workbench/shell.ts'
STYLE_CSS = REPO / 'apps/workbench/style.css'
LEDGER = REPO / 'design-lab/config/task-ledger-r3.json'
OUT_MD = REPO / 'docs/history/archive-2026-10-19/current-records/UI-DESKTOP-RECONCILIATION-2026-10-09.md'

sys.path.insert(0, str(REPO / 'design-lab/scripts'))
from verify_capability_self_description import (  # noqa: E402
    dispatched_routes,
    route_is_dispatched,
)

# ---------------------------------------------------------------------------
# 包屏 →  shipped 视图 的映射决定。status 词汇：
#   LANDED_READ_REAL  这一屏有自己的视图，且读的是服务真的 dispatch 的路由
#   LANDED_SPEC       这一屏有自己的视图，且按定义不需要后端（规格/状态面）
#   READ_ELSEWHERE    数据已经能从别的视图真实读回，但包里的这一屏还不是独立视图
#   NOT_LANDED        本批没做，指向具名的后续任务卡
# routes 里的每一条都会被 dispatch 集合核验；NOT_LANDED/READ_ELSEWHERE 必须给 reason
# 且必须给 replaces（currentExecution 里真实存在的任务 id）。
# ---------------------------------------------------------------------------
SCREEN_MAP = [
    dict(screen='01', pack_route='catalog', title='能力目录', status='LANDED_READ_REAL',
         view='capabilities', routes=['/api/capabilities'],
         note='GET /api/capabilities 的读回此前只嵌在仪表盘里，本批给它自己的入口与标题。'
              '2026-10-09 U03 追加许可/处置/存在状态/证据级四个前置过滤，候选值取自本批'
              '读回本身；七轴当前在候选分类账里全部为空（37 条 joined 记录带的是空容器），'
              '所以轴筛选没有可列的取值，界面如实显示"未分类"而不代填。'),
    dict(screen='02', pack_route='capability', title='能力详情', status='LANDED_READ_REAL',
         view='capabilities', routes=['/api/capabilities'],
         note='U03 落地为能力行内的展开面：七轴取值（有值 / 未分类 / 无字段三种说法分开）、'
              '资格判定与理由、许可与权利、证据级、反例与不适用。它是行内展开而不是独立'
              '路由；「使用此能力」仍禁用，把能力落成目标包属 U05/T10。'),
    dict(screen='03', pack_route='input', title='输入与目标', status='LANDED_READ_REAL',
         view='intake', routes=['/api/projects/{id}/briefs', '/api/projects/{id}/assets'],
         note='U04 落地：项目选择走真实台账，简报经 design.ts createBrief()（校验与幂等键'
              '只有一份）写入，参考清单读回本项目真实资产（含权利与版本）。精确文案/锁比例/'
              '锁位置/编辑范围与参考职责**编排进 constraints 文本**，因为合同只有 title/goals/'
              'constraints/reference_asset_ids 四项，界面不假装持久化不存在的字段。'
              '音频/视频/3D 上传禁用：导入路由只接受不超过 32 MiB 的 PNG/JPEG。'),
    dict(screen='04', pack_route='analysis', title='分析与方案', status='LANDED_READ_REAL',
         view='analysis', routes=['/api/projects/{id}/design-layer'],
         note='U04 屏 04 落地：现行方向、方法/偏好字段、来源与知识引用（简报版本/目标/约束/'
              '引用数/spec 摘要）、设计系统绑定逐条从设计层读回；纠正走 design.ts '
              'reviseDirection()（与遗留表单同一规则，追加新版本不改旧字节）。'
              '"已识别结构与推断"一格明确写**无来源**：analysis/plan_to_rir 无调用方，'
              '接通前本页不画推断节点。'),
    dict(screen='05', pack_route='plan', title='目标生成包', status='LANDED_READ_REAL',
         view='plan', routes=['/api/projects/{id}/native-plans', '/api/projects/{id}/assets'],
         note='U05 落地：界面按已记录对象编排 reconstruction-ir/v1（画布取底图真实尺寸、'
              'raster.path 用完整 img-ID、inferred=false 因为它是用户勾选而非检测推断），'
              '提交 POST native-plans 只排队不启动宿主。剩余：结构/文字/路径节点不编排'
              '（analysis/plan_to_rir 桥没有生产调用方，仓库里只有 design-lab/tests 在调），以及 DL-FINAL-T10 的可校正计划版本。'),
    dict(screen='06', pack_route='running', title='制作与核验', status='READ_ELSEWHERE',
         view='project-detail', routes=[r'/api/projects/([0-9a-f]{32})/tasks(?:\?after=((?:native-)?job-[0-9a-f]{64}))?'],
         replaces='DL-UI-U06',
         reason='任务与事件已在项目详情里真实读回，运行控制（占用/预算/暂停/取消）按 U06 接。'),
    dict(screen='07', pack_route='recovery', title='恢复与对账', status='NOT_LANDED',
         replaces='DL-UI-U06',
         reason='恢复面依赖 T11 的租约/幂等/对账语义，先于它画出来就是假动作。'),
    dict(screen='08', pack_route='results', title='成果目录', status='READ_ELSEWHERE',
         view='deliverables', routes=['/api/projects', '/api/projects/{id}/bundles'],
         replaces='DL-UI-U07',
         reason='交付包列表已真实读回；包要求的"分析/生成包/草稿/测试导出/正式交付"分型检索按 U07。'),
    dict(screen='09', pack_route='result', title='产物与改稿', status='READ_ELSEWHERE',
         view='deliverables', routes=[r'/api/projects/([0-9a-f]{32})/native-assets(?:\?after=(native-[0-9a-f]{64}))?'],
         replaces='DL-UI-U07',
         reason='原生资产与版本已可读回并校验；局部 patch 的新版本流程按 U07 接进新壳。'),
    dict(screen='10', pack_route='jury', title='版本对比与评审', status='READ_ELSEWHERE',
         view='evidence', routes=['/api/projects/{id}/jury'],
         replaces='DL-UI-U08',
         reason='Jury 的读回与真人表单已在证据系统/项目详情里，版本差分对比与回执失效按 U08。'),
    dict(screen='11', pack_route='delivery', title='交付预检', status='READ_ELSEWHERE',
         view='preflight-qa', routes=['/api/task-preflight'],
         replaces='DL-UI-U08',
         reason='预检/权利/BOM 的读回已存在；测试范围与正式交付范围分离按 U08/T14。'),
    dict(screen='12', pack_route='feedback', title='反馈与知识候选', status='NOT_LANDED',
         replaces='DL-UI-U09',
         reason='候选与回执要先有 T16 的公共合同，不能先画一个把观察写进 localStorage 的假面。'),
    dict(screen='13', pack_route='teaching', title='教学需求', status='NOT_LANDED',
         replaces='DL-UI-U10',
         reason='教学接同一制作流依赖 U05/T17，属 B4。'),
    dict(screen='14', pack_route='connections', title='连接与诊断', status='READ_ELSEWHERE',
         view='settings', routes=['/api/health', '/api/environment'],
         replaces='DL-UI-U11',
         reason='健康与环境读回已在系统设置里；宿主在线探测仍缺路由，按 U11 处理退出与降级。'),
    dict(screen='15', pack_route='states', title='界面状态', status='LANDED_SPEC',
         view='ui-states',
         note='状态面：每个状态写清它由哪段代码产生、必须给什么下一步，不发请求所以不可能有编造记录。'),
    dict(screen='16', pack_route='components', title='组件规范', status='LANDED_SPEC',
         view='ui-components',
         note='组件面：令牌/药丸/按钮/输入/列表/表格/状态块，页面上出现的类名都有真实调用点。'),
    dict(screen='17', pack_route='catalog', title='浅色能力目录', status='LANDED_READ_REAL',
         view='capabilities', routes=['/api/capabilities'], theme='ui2026 + light',
         note='同一份读回换色板：新包配色做成可选主题，不覆盖既有配色；默认仍是 DESIGN-LAB 色板。'),
]

# pack design_tokens.json 的键 → 仓内 --uif-* 原语名。逐条核验，不做"就近取整"。
TOKEN_PAIRS = {
    'dark.background': '--uif-dark-bg', 'dark.surface': '--uif-dark-surface',
    'dark.raised': '--uif-dark-raised', 'dark.text': '--uif-dark-text',
    'dark.muted': '--uif-dark-muted', 'dark.border': '--uif-dark-border',
    'dark.accent': '--uif-dark-accent', 'dark.accent_text': '--uif-dark-accent-text',
    'dark.success': '--uif-dark-success', 'dark.warning': '--uif-dark-warning',
    'dark.danger': '--uif-dark-danger',
    'light.background': '--uif-light-bg', 'light.surface': '--uif-light-surface',
    'light.raised': '--uif-light-raised', 'light.text': '--uif-light-text',
    'light.muted': '--uif-light-muted', 'light.border': '--uif-light-border',
    'light.accent': '--uif-light-accent', 'light.accent_text': '--uif-light-accent-text',
    'light.success': '--uif-light-success', 'light.warning': '--uif-light-warning',
    'light.danger': '--uif-light-danger',
    'typography.size_css_px.h1': '--uif-font-h1', 'typography.size_css_px.h2': '--uif-font-h2',
    'typography.size_css_px.h3': '--uif-font-h3', 'typography.size_css_px.body': '--uif-font-body',
    'typography.size_css_px.small': '--uif-font-small',
    'typography.size_css_px.micro': '--uif-font-micro',
    'typography.body_line_height': '--uif-body-line-height',
    'radius_css_px.controls': '--uif-radius-control', 'radius_css_px.cards': '--uif-radius-card',
    'radius_css_px.hero': '--uif-radius-hero',
    'layout.sidebar': '--uif-sidebar', 'layout.desktop_gutter': '--uif-gutter-desktop',    'layout.compact_gutter': '--uif-gutter-compact',
    'motion.recommended_ms.0': '--uif-motion-fast', 'motion.recommended_ms.1': '--uif-motion-base',
}

STATUS_LABEL = {
    'LANDED_READ_REAL': '已落地 · 读真实路由',
    'LANDED_SPEC': '已落地 · 规格面（不需要后端）',
    'READ_ELSEWHERE': '数据已可读回 · 尚无独立屏',
    'NOT_LANDED': '本批未落地',
}


def flatten(node, prefix=''):
    out = {}
    if isinstance(node, dict):
        for k, v in node.items():
            out.update(flatten(v, f'{prefix}.{k}' if prefix else k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out.update(flatten(v, f'{prefix}.{i}'))
    else:
        out[prefix] = node
    return out


#: Views that come from the R2 pack rather than from R1's screen_map.json. Without this the
#: table would label them "保留的旧技术路径", which is a different claim from "R2 §x asked
#: for it and R1 has no screen for it".
R2_VIEW_SOURCES = {
    'records': 'R2 §2/§7 制作记录与待继续（R1 17 屏里没有对应屏）',
    'ui-states': 'R2 §10 状态矩阵',
    'ui-components': 'R2 §11 组件与令牌',
}


def read_route_table():
    src = SHELL_TS.read_text(encoding='utf-8')
    start = src.index('export const ROUTE_VIEWS')
    end = src.index('export type RouteView', start)
    rows = re.findall(
        r"\{ hash: '([^']*)', view: '([^']*)', label: '([^']*)', entry: '([^']*)' \}",
        src[start:end])
    if len(rows) < 12:
        raise SystemExit(f'ROUTE_VIEWS 只解析到 {len(rows)} 行，提取式已失效，不要用这张表下结论')
    return [{'hash': h, 'view': v, 'label': l, 'entry': e} for h, v, l, e in rows]


def read_css_custom_properties():
    css = STYLE_CSS.read_text(encoding='utf-8')
    return dict(re.findall(r'(--[a-z0-9-]+):\s*([^;]+);', css))


def pick(flat, dotted):
    return flat.get(dotted)


def git(*args):
    return subprocess.run(['git', '-C', str(REPO), *args], capture_output=True,
                          text=True, encoding='utf-8', errors='replace').stdout.strip()


def build():
    screens = json.loads((UI_INPUTS / 'screen_map.json').read_text(encoding='utf-8'))
    tokens = json.loads((UI_INPUTS / 'design_tokens.json').read_text(encoding='utf-8'))
    flat = flatten(tokens)
    css = read_css_custom_properties()
    routes = dispatched_routes(REPO)
    # 谓词与仓库既有的自我描述门共用，不自己发明第二套匹配。
    table = read_route_table()
    # project-detail 是 B07 的参数化路由 `/projects/:id`，按设计**不在** ROUTE_VIEWS
    # 里（它没有自己的导航按钮，只能从项目行进），但它确实是 shipped 视图。
    views = {row['view'] for row in table} | {'project-detail'}
    ledger = json.loads(LEDGER.read_text(encoding='utf-8'))
    task_ids = {t['id'] for t in ledger['currentExecution']['tasks']}

    problems = []

    desktop = [s for s in screens if not s.get('mobile')]
    pack_ids = {s['id'] for s in desktop}
    mapped_ids = {f"{row['screen']}_{row['pack_route']}" for row in SCREEN_MAP}
    declared = {s['id'].split('_')[0] for s in desktop}
    missing = sorted(declared - {row['screen'] for row in SCREEN_MAP})
    if missing:
        problems.append(f'包里的桌面屏没有全部对账：{missing}')

    for row in SCREEN_MAP:
        if row['status'] in ('LANDED_READ_REAL', 'LANDED_SPEC', 'READ_ELSEWHERE'):
            if row.get('view') not in views:
                problems.append(f"屏 {row['screen']} 声称视图 {row.get('view')}，"
                                f'但 ROUTE_VIEWS 里没有这一行')
        for route in row.get('routes', []):
            # 两种写法都接受：人类形态 `/api/projects/{id}/jury`（交给仓库既有的
            # 逐段谓词），或**逐字抄自 dispatched 集合的正则形态**（当服务把游标尾巴
            # 写进末段时，末段就不是纯字面量，谓词会拒绝——那种情况下逐字引用）。
            if not (route_is_dispatched(route, routes) or route in routes):
                problems.append(f"屏 {row['screen']} 引用 {route}，"
                                '它既不是 dispatch 路由的人类形态，也不是逐字形态')
        if row['status'] in ('NOT_LANDED', 'READ_ELSEWHERE'):
            if not row.get('reason', '').strip():
                problems.append(f"屏 {row['screen']} 未落地却没有原因：读者无法核对的空不是披露")
            if row.get('replaces') not in task_ids:
                problems.append(f"屏 {row['screen']} 指向 {row.get('replaces')}，"
                                f'它不在 currentExecution 的任务集合里')

    # 令牌：包的每个登记值都必须与 CSS 里的原语逐字相等。
    token_rows = []
    for dotted, prop in TOKEN_PAIRS.items():
        want = pick(flat, dotted)
        got = css.get(prop)
        if want is None:
            problems.append(f'design_tokens.json 里没有 {dotted}，映射表已过期')
            continue
        if got is None:
            problems.append(f'{prop} 未落地，{dotted} 只写在映射表里')
            continue
        gotv = got.strip()
        if dotted.endswith('body_line_height'):
            expect = str(want)                      # 1.65 没有单位
        elif dotted.startswith('motion.recommended_ms'):
            expect = f'{want}ms'                    # 140 / 220 是毫秒
        elif isinstance(want, str):
            expect = str(want)                      # 颜色本身就是字符串
        else:
            expect = f'{want}px'                    # 尺寸类整数按 CSS 像素落地
        if gotv.lower() != expect.lower():
            problems.append(f'{prop} = {gotv}，包里 {dotted} = {expect}')
        token_rows.append((dotted, prop, expect, gotv))

    # 反向映射：每个 shipped 视图对应哪些包屏。没有对应包屏的槽位不是缺陷，
    # 而是"保留的旧技术路径"，表里如实这么写。
    view_to_screens = {}
    for row in SCREEN_MAP:
        if row.get('view'):
            view_to_screens.setdefault(row['view'], []).append(f"{row['screen']} {row['title']}")
    return table, routes, problems, token_rows, view_to_screens, desktop


def render(table, routes, problems, token_rows, view_to_screens, desktop, head, dirty):
    lines = [
        '# 桌面 UI 对账 · 20261009 包屏 ↔ 实际视图 ↔ 真实路由',
        '',
        f'DL-UI-U01 交付物。生成器：`scripts/audit_ui_desktop_reconcile_20261009.py`'
        f'（重跑即重算，手写数字不会被接受）。',
        '',
        f'- 观察 HEAD：`{head}`',
        f'- 工作树：{"DIRTY（本地未提交，见 AGENTS.md 2026-10-09 归档说明）" if dirty else "CLEAN"}',
        f'- 服务 dispatch 的路由条数：{len(routes)}',
        f'- ROUTE_VIEWS 条数：{len(table)}（三入口 + 辅助分组）',
        f'- 包内桌面屏条数：{len(desktop)}',
        '',
        '> 本表是**结构对账**，不是产品验收。"已落地"只说明该视图存在且读的是服务真的',
        '> dispatch 的路由；不说明 E3/E4/E5，不说明真实宿主、真人评审或三方实联。',
        '',
        '## 屏 ↔ 视图 ↔ 路由',
        '',
        '| 屏 | 包路由 | 界面 | 状态 | 视图 | 真实路由 | 取代/后续 | 说明或原因 |',
        '|---|---|---|---|---|---|---|---|',
    ]
    for row in SCREEN_MAP:
        lines.append('| {screen} | `{pack_route}` | {title} | {status} | {view} | {routes} '
                     '| {replaces} | {note} |'.format(
                         screen=row['screen'], pack_route=row['pack_route'], title=row['title'],
                         status=STATUS_LABEL[row['status']],
                         view=('`' + row['view'] + '`') if row.get('view') else '—',
                         routes=', '.join('`%s`' % r for r in row.get('routes', [])) or '—',
                         replaces=('`%s`' % row['replaces']) if row.get('replaces') else '—',
                         note=row.get('note') or row.get('reason') or ''))
    lines += [
        '',
        '## 三入口分组（布局按新包执行，配色不覆盖）——旧槽位 ↔ 新包屏',
        '',
        '方向是**旧的每个槽位都要有去处**：能对上包屏的写包屏号，对不上的写明是保留的',
        '旧技术路径，不假装新包里也有它。',
        '',
        '| 入口 | 槽位 | 视图 | hash | 对应包屏 |',
        '|---|---|---|---|---|',
    ]
    for row in table:
        provenance = (view_to_screens.get(row['view'])
                      or R2_VIEW_SOURCES.get(row['view'])
                      or '— 保留的旧技术路径（无对应包屏）')
        lines.append('| %s | %s | `%s` | `%s` | %s |'
                     % (row['entry'], row['label'], row['view'],
                        row['hash'] or '(空 hash = 遗留工作台)', provenance))
    lines += [
        '',
        '## 20261009 基线令牌 ↔ 已落地原语（逐条相等）',
        '',
        '| 包内字段 | CSS 原语 | 包值 | 落地值 |',
        '|---|---|---|---|',
    ]
    for dotted, prop, want, got in token_rows:
        lines.append('| `%s` | `%s` | `%s` | `%s` |' % (dotted, prop, want, got))
    lines += [
        '',
        '配色轴的落地方式：包的值做成 **可选主题**（`?palette=ui2026`，明暗正交参数',
        '`?scheme=light`），既有 DESIGN-LAB 色板保持默认且字节不变；品牌蓝家族与',
        '`--border-strong` 这类**被实测修正过的地板值**不随色板切换，见 style.css 同段注释。',
        '',
    ]
    lines += ['## 对账结论', '']
    lines += [f'- 问题：{len(problems)} 条' if problems else '- 问题：0 条（本表可复核）']
    for problem in problems:
        lines.append(f'  - {problem}')
    lines.append('')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true',
                        help='只比对已提交的 MD 与重新生成的结果，不写文件')
    args = parser.parse_args(argv)

    table, routes, problems, token_rows, view_to_screens, desktop = build()
    head = git('rev-parse', 'HEAD')
    dirty = bool(git('status', '--porcelain', '--', 'apps/workbench', 'src/design_lab',
                     'design-lab/config/task-ledger-r3.json'))
    text = render(table, routes, problems, token_rows, view_to_screens, desktop, head, dirty)
    if args.check:
        current = OUT_MD.read_text(encoding='utf-8') if OUT_MD.is_file() else ''
        if current != text:
            print('UI_RECONCILIATION_DRIFT: 重新生成的对账与已提交的 MD 不一致')
            return 1
    else:
        OUT_MD.parent.mkdir(parents=True, exist_ok=True)
        OUT_MD.write_text(text, encoding='utf-8', newline='\n')
        print(f'wrote {OUT_MD.relative_to(REPO)}')
    if problems:
        for problem in problems:
            print(f'UI_RECONCILIATION: {problem}')
        print(f'UI_RECONCILIATION_FAILED: {len(problems)} 条对不上')
        return 1
    print(f'UI_RECONCILIATION: OK（{len(SCREEN_MAP)} 屏 / {len(table)} 槽 / '
          f'{len(routes)} 路由 / {len(token_rows)} 令牌逐条相等）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
