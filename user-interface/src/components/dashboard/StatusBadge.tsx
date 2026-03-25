import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

type StatusTone = "ok" | "error" | "warn" | "info" | "neutral";

interface StatusBadgeProps {
  tone?: StatusTone;
  className?: string;
  children: ReactNode;
}

const toneClasses: Record<StatusTone, string> = {
  ok: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  error: "border-red-500/35 bg-red-500/15 text-red-300",
  warn: "border-amber-500/35 bg-amber-500/15 text-amber-300",
  info: "border-sky-500/35 bg-sky-500/15 text-sky-300",
  neutral: "border-slate-600/80 bg-slate-700/60 text-slate-300",
};

export function StatusBadge({ tone = "neutral", className, children }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.14em]",
        toneClasses[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
