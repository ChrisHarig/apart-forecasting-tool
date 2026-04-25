import type { ReactNode } from "react";

interface PanelProps {
  title?: string;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Panel({ title, eyebrow, action, children, className = "" }: PanelProps) {
  return (
    <section className={`rounded-lg border border-white/10 bg-ink-900/88 shadow-glow backdrop-blur ${className}`}>
      {(title || eyebrow || action) && (
        <div className="flex items-start justify-between gap-4 border-b border-white/10 px-4 py-3">
          <div>
            {eyebrow && <p className="text-[0.68rem] font-semibold uppercase text-red-300">{eyebrow}</p>}
            {title && <h2 className="mt-1 text-sm font-semibold text-slate-100">{title}</h2>}
          </div>
          {action}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}
