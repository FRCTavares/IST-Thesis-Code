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
    const trackerFps = telemetry?.det_fps ?? 0;
    const hasTelemetry = Boolean(telemetry);

    return (
        <PanelShell
            title="Tracking Metrics"
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
                    {!hasTelemetry && (
                        <div className="mb-2 rounded-md border border-slate-700/70 bg-slate-900/45 px-2.5 py-2 text-[11px] text-slate-400">
                            No live telemetry yet. Tracking metrics will populate when stream is available.
                        </div>
                    )}
                    <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
                        <MetricCard
                            label="Active Tracks"
                            value={String(activeTracks)}
                            detail={`Currently tracked objects`}
                            tone="ok"
                        />
                        <MetricCard
                            label="Tracker FPS"
                            value={fmt(trackerFps, 1)}
                            detail={`Track updates per second`}
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
