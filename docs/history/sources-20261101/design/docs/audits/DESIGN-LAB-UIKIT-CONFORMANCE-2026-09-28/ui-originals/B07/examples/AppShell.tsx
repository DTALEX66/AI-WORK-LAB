import React from "react";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div data-theme="design_lab" className="app-shell">
      <aside className="sidebar">{/* DESIGN-LAB primary navigation */}</aside>
      <main className="app-main">
        <header className="topbar">{/* search / notifications / account */}</header>
        <section className="page-content">{children}</section>
      </main>
    </div>
  );
}
