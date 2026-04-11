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
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-zinc-700/70">
            <div
                className={`h-full transition-all ${warning ? "bg-gradient-to-r from-amber-400 to-red-500" : "bg-gradient-to-r from-zinc-500 to-zinc-300"}`}
                style={{ width: `${pct}%` }}
            />
        </div>
    );
}

export function SystemMetricsGrid({ snapshot }: SystemMetricsGridProps) {
    return (
        <PanelShell title="System Metrics" className="">
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
        </PanelShell>
    );
}
