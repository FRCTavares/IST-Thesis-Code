import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

interface PanelShellProps {
  title?: string;
  action?: ReactNode;
  className?: string;
  contentClassName?: string;
  children: ReactNode;
}

export function PanelShell({ title, action, className, contentClassName, children }: PanelShellProps) {
  return (
    <section className={cn("rounded-lg border border-slate-700/80 bg-slate-800/70", className)}>
      {(title || action) && (
        <div className="flex items-center justify-between gap-2 border-b border-slate-700/70 px-3 py-2">
          {title ? <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">{title}</div> : <span />}
          {action}
        </div>
      )}
      <div className={cn("p-3", contentClassName)}>{children}</div>
    </section>
  );
}
