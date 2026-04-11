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
    <section className={cn("panel-shell rounded-lg border border-zinc-700/80 bg-zinc-800/70", className)}>
      {(title || action) && (
        <div className="panel-shell-header flex h-10 items-center justify-between gap-2 border-b border-zinc-700/70 px-3">
          {title ? <div className="text-[11px] font-semibold uppercase tracking-[0.16em] leading-none text-zinc-400">{title}</div> : <span />}
          {action}
        </div>
      )}
      <div className={cn("panel-shell-content p-3", contentClassName)}>{children}</div>
    </section>
  );
}
