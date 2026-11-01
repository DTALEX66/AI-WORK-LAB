import React from "react";

type Props = {
  title: string;
  description?: string;
};

export function PageTemplate({ title, description }: Props) {
  return (
    <>
      <header className="page-header">
        <div>
          <h1>{title}</h1>
          {description && <p>{description}</p>}
        </div>
        <div className="page-actions">{/* primary action */}</div>
      </header>

      <section className="responsive-grid">
        {/* KPI / cards / tables / graphs */}
      </section>
    </>
  );
}
