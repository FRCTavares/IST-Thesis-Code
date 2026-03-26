import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { MetricsSnapshot } from "@/types/dashboard";
import { fmt } from "@/features/dashboard/utils/metrics";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { PanelShell } from "@/components/dashboard/PanelShell";

interface SystemMetricsGridProps {
    snapshot: MetricsSnapshot | null;
}

function HeatBar({ value, threshold }: { value: number | null | undefined; threshold: number }) {
    const pct = value === null || value === undefined ? 0 : Math.max(0, Math.min(100, Number(value)));
    const warning = pct >= threshold;

    return (
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-700/70">
            <div
                className={`h-full transition-all ${warning ? "bg-gradient-to-r from-amber-400 to-red-500" : "bg-gradient-to-r from-sky-500 to-emerald-500"}`}
                style={{ width: `${pct}%` }}
            />
        </div>
    );
}

export function SystemMetricsGrid({ snapshot }: SystemMetricsGridProps) {
    const [collapsed, setCollapsed] = useState(false);
    const hasSnapshot = Boolean(snapshot);

    return (
        <PanelShell
            title="System Metrics"
            className="mt-3"
            action={
                <button
                    type="button"
                    onClick={() => setCollapsed((prev) => !prev)}
                    className="inline-flex items-center gap-1 rounded-md border border-slate-700/80 bg-slate-900/70 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-300 hover:border-slate-500 hover:text-slate-100"
                >
                    {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                    {collapsed ? "Open" : "Collapse"}
                </button>
            }
        >
            {!collapsed && (
                <>
                    {!hasSnapshot && (
                        <div className="mb-2 rounded-md border border-slate-700/70 bg-slate-900/45 px-2.5 py-2 text-[11px] text-slate-400">
                            No live telemetry yet. System load and temperature metrics are waiting for updates.
                        </div>
                    )}
                    <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                        <MetricCard
                            label="CPU Load"
                            value={fmt(snapshot?.cpu_percent_inst, 1, " %")}
                            detail={`10s avg ${fmt(snapshot?.cpu_percent_10s_avg, 1)} %`}
                            tone={(snapshot?.cpu_percent_inst ?? 0) >= 88 ? "warn" : "default"}
                            footer={<HeatBar value={snapshot?.cpu_percent_inst} threshold={88} />}
                        />
                        <MetricCard
                            label="Memory Use"
                            value={
                                snapshot?.mem_percent_inst !== null && snapshot?.mem_percent_inst !== undefined
                                    ? `${fmt(snapshot?.mem_percent_inst, 1, " %")} / ${fmt(snapshot?.mem_used_mb_inst, 0, " MB")}`
                                    : "--"
                            }
                            detail={`10s avg ${fmt(snapshot?.mem_percent_10s_avg, 1)} %`}
                            tone={(snapshot?.mem_percent_inst ?? 0) >= 92 ? "warn" : "default"}
                            footer={<HeatBar value={snapshot?.mem_percent_inst} threshold={92} />}
                        />
                        <MetricCard
                            label="CPU Temp"
                            value={fmt(snapshot?.temp_c_inst, 1, " C")}
                            detail={`10s avg ${fmt(snapshot?.temp_c_10s_avg, 1)} C`}
                            tone={(snapshot?.temp_c_inst ?? 0) >= 75 ? "warn" : "default"}
                            footer={<HeatBar value={snapshot?.temp_c_inst ? (snapshot?.temp_c_inst / 85) * 100 : 0} threshold={92} />}
                        />
                    </div>
                </>
            )}
        </PanelShell>
    );
}
