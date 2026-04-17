import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { DashboardTelemetry } from "@/types/dashboard";
import { fmt } from "@/features/dashboard/utils/metrics";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { PanelShell } from "@/components/dashboard/PanelShell";

interface TrackingMetricsGridProps {
    telemetry: DashboardTelemetry | null;
}

export function TrackingMetricsGrid({ telemetry }: TrackingMetricsGridProps) {
    const [collapsed, setCollapsed] = useState(false);
    const activeTracks = telemetry?.tracks.length ?? 0;
    const totalDetections = telemetry?.detections.length ?? 0;
    const associationRate = totalDetections > 0 ? (activeTracks / totalDetections) * 100 : 0;
    const detectionRateFps = telemetry?.det_out_fps ?? 0;

    return (
        <PanelShell
            title="Tracking Metrics"
            className="mt-3"
            action={
                <button
                    type="button"
                    onClick={() => setCollapsed((prev) => !prev)}
                    className="inline-flex items-center gap-1 rounded-md border border-zinc-700/80 bg-zinc-900/70 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-300 hover:border-zinc-500 hover:text-zinc-100"
                >
                    {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                    {collapsed ? "Open" : "Collapse"}
                </button>
            }
        >
            {!collapsed && (
                <>
                    <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
                        <MetricCard
                            label="Active Tracks"
                            value={String(activeTracks)}
                            detail={`Currently tracked objects`}
                            tone="ok"
                        />
                        <MetricCard
                            label="Detection Rate"
                            value={fmt(detectionRateFps, 1)}
                            detail={`Detection messages per second`}
                            tone="info"
                        />
                        <MetricCard
                            label="Association Rate"
                            value={fmt(associationRate, 1, " %")}
                            detail={`${activeTracks} / ${totalDetections} detections`}
                            tone={associationRate > 60 ? "ok" : associationRate > 30 ? "warn" : "default"}
                        />
                        <MetricCard
                            label="Target"
                            value={telemetry?.target !== null && telemetry?.target !== undefined ? `#${telemetry.target}` : "--"}
                            detail={`Selected track ID`}
                            tone="info"
                        />
                    </div>
                </>
            )}
        </PanelShell>
    );
}
