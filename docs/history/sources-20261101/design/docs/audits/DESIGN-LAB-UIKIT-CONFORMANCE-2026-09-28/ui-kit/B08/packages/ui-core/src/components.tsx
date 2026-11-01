import React from "react";
import type { Theme, NavItem } from "./types";

export function AppShell(props: {
  brand: string;
  subtitle: string;
  theme: Theme;
  nav: readonly NavItem[];
  active: string;
  onNavigate: (id: string) => void;
  children: React.ReactNode;
}) {
  const { brand, subtitle, theme, nav, active, onNavigate, children } = props;
  const vars = {
    "--bg": theme.bg, "--sidebar": theme.sidebar, "--surface": theme.surface,
    "--surface2": theme.surface2, "--border": theme.border, "--primary": theme.primary,
    "--secondary": theme.secondary, "--text": theme.text, "--muted": theme.muted,
    "--success": theme.success, "--warning": theme.warning, "--error": theme.error,
  } as React.CSSProperties;

  return (
    <div className="app-shell" style={vars}>
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">{brand.slice(0,2).toUpperCase()}</div>
          <div>
            <div className="brand-name">{brand}</div>
            <div className="brand-subtitle">{subtitle}</div>
          </div>
        </div>
        <nav>
          {nav.map(item => (
            <button key={item.id} className={"nav-item " + (item.id===active ? "active":"")}
              onClick={() => onNavigate(item.id)}>
              <span className="nav-dot"/><span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="avatar">A</div>
          <div><strong>Alex</strong><small>Personal Workspace</small></div>
        </div>
      </aside>
      <main className="main-shell">
        <header className="topbar">
          <div className="search">⌘ K&nbsp;&nbsp; 搜索 / Search</div>
          <div className="top-actions"><button>通知</button><button>帮助</button><button>账户</button></div>
        </header>
        <section className="page-content">{children}</section>
      </main>
    </div>
  );
}

export function PageHeader({title, description, action}:{title:string;description:string;action?:string}) {
  return <div className="page-header"><div><h1>{title}</h1><p>{description}</p></div>
    {action && <button className="primary-btn">{action}</button>}</div>;
}
export function KPI({value,label,accent="primary"}:{value:string;label:string;accent?:"primary"|"success"|"warning"|"error"}) {
  return <div className="card kpi"><strong className={accent}>{value}</strong><span>{label}</span></div>;
}
export function Card({title,children,className=""}:{title?:string;children?:React.ReactNode;className?:string}) {
  return <div className={"card "+className}>{title && <div className="card-title">{title}</div>}{children}</div>;
}
export function DataTable({headers,rows}:{headers:string[];rows:(string|React.ReactNode)[][]}) {
  return <div className="table-wrap"><table><thead><tr>{headers.map(h=><th key={h}>{h}</th>)}</tr></thead>
  <tbody>{rows.map((r,i)=><tr key={i}>{r.map((c,j)=><td key={j}>{c}</td>)}</tr>)}</tbody></table></div>;
}
export function Status({tone="success",children}:{tone?:"success"|"warning"|"error"|"info";children:React.ReactNode}) {
  return <span className={"status "+tone}>{children}</span>;
}
export function MiniChart({values=[20,40,35,60,55,72,68,80]}:{values?:number[]}) {
  const points=values.map((v,i)=>`${i*(100/(values.length-1))},${100-v}`).join(" ");
  return <svg className="mini-chart" viewBox="0 0 100 100" preserveAspectRatio="none"><polyline points={points} fill="none" stroke="var(--primary)" strokeWidth="3"/></svg>;
}
export function NodeGraph({center="Core",labels=["A","B","C","D","E","F"]}:{center?:string;labels?:string[]}) {
  const coords=[[50,12],[83,28],[88,68],[50,88],[16,68],[18,28]];
  return <svg className="node-graph" viewBox="0 0 100 100">
    {labels.slice(0,6).map((_,i)=><line key={"l"+i} x1="50" y1="50" x2={coords[i][0]} y2={coords[i][1]} stroke="var(--border)" strokeWidth="1.2"/>)}
    <circle cx="50" cy="50" r="8" fill="var(--primary)"/><text x="50" y="52" textAnchor="middle" fontSize="5" fill="white">{center}</text>
    {labels.slice(0,6).map((l,i)=><g key={l}><circle cx={coords[i][0]} cy={coords[i][1]} r="5" fill="var(--surface2)" stroke="var(--secondary)" strokeWidth="1"/>
    <text x={coords[i][0]} y={coords[i][1]+1.5} textAnchor="middle" fontSize="4" fill="var(--text)">{l}</text></g>)}
  </svg>;
}
