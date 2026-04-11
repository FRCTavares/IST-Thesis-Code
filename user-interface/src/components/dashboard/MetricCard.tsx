import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

interface MetricCardProps {
  label: string;
  value: string;
  detail?: string;
  tone?: "default" | "ok" | "warn" | "error" | "info";
  className?: string;
  footer?: ReactNode;
}

const valueTone: Record<NonNullable<MetricCardProps["tone"]>, string> = {
  default: "text-zinc-100",
  ok: "text-emerald-300",
  warn: "text-amber-300",
  error: "text-red-300",
  info: "text-zinc-200",
};

export function MetricCard({ label, value, detail, tone = "default", className, footer }: MetricCardProps) {
  return (
    <div className={cn("rounded-md border border-zinc-700/80 bg-zinc-900/55 p-2.5", className)}>
      <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">{label}</div>
      <div className={cn("mt-1 text-xl font-semibold leading-none", valueTone[tone])}>{value}</div>
      {detail ? <div className="mt-1.5 font-mono text-[11px] text-zinc-400">{detail}</div> : null}
      {footer}
    </div>
  );
}
