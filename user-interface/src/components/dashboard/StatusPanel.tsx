import { Download, Gauge, Wifi, X } from "lucide-react";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { PanelShell } from "@/components/dashboard/PanelShell";
import { StatusBadge } from "@/components/dashboard/StatusBadge";
import { ModelTrackerSelector } from "@/components/dashboard/ModelTrackerSelector";
import { Button } from "@/components/ui/button";
import { fmt } from "@/features/dashboard/utils/metrics";
import type { DashboardDataMode, DashboardModel, DashboardTelemetry, DashboardTracker, MetricsSnapshot } from "@/types/dashboard";

interface StatusPanelProps {
  status: string;
  mode: DashboardDataMode;
  telemetry: DashboardTelemetry | null;
  snapshot: MetricsSnapshot | null;
  activeModel?: DashboardModel;
  activeTracker?: DashboardTracker;
  onModelSwitch?: (model: DashboardModel) => Promise<void>;
  onTrackerSwitch?: (tracker: DashboardTracker) => Promise<void>;
  onExport?: () => void;
  onCloseSidebar?: () => void;
  isModelSwitching?: boolean;
  isTrackerSwitching?: boolean;
  controlStatus?: string;
}

export function StatusPanel({
  status,
  mode,
  telemetry,
  snapshot,
  activeModel = "yolov6n",
  activeTracker = "sort",
  onModelSwitch,
  onTrackerSwitch,
  onExport,
  onCloseSidebar,
  isModelSwitching = false,
  isTrackerSwitching = false,
  controlStatus,
}: StatusPanelProps) {
  const hasTelemetry = Boolean(telemetry);
  const statusLower = status.toLowerCase();
  const explicitlyDisconnected = /(disconnected|retry|error|fail|closed|closing|connecting)/.test(statusLower);
  const explicitlyConnected = /(connected|live|open)/.test(statusLower);
  const isHealthy = hasTelemetry || (explicitlyConnected && !explicitlyDisconnected);
  const tone = isHealthy ? "ok" : "warn";

  return (
    <aside className="h-full">
      <PanelShell
        title="Operations Panel"
        className="flex h-full flex-col"
        action={
          <div className="flex items-center gap-2">
            <StatusBadge tone={tone}>{tone === "ok" ? "Healthy" : "Degraded"}</StatusBadge>
            {onCloseSidebar && (
              <button
                type="button"
                onClick={onCloseSidebar}
                className="h-8 w-8 rounded-md border border-red-500/45 bg-red-500/10 text-red-300 transition-all hover:border-red-400/70 hover:bg-red-500/18"
                aria-label="Close side panel"
                title="Close side panel"
              >
                <X className="mx-auto h-4 w-4" />
              </button>
            )}
          </div>
        }
        contentClassName="flex-1 space-y-5"
      >
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-slate-200">
            <Wifi className="h-4 w-4 text-sky-300" />
            <span className="truncate">{status}</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <MetricCard label="Mode" value={mode.toUpperCase()} tone="info" className="p-2" />
            <MetricCard
              label="Stream"
              value={hasTelemetry ? "LIVE" : "WAIT"}
              tone={hasTelemetry ? "ok" : "warn"}
              className="p-2"
            />
          </div>
        </div>

        <div className="border-t border-slate-700/70 pt-4">
          <div className="mb-2 flex items-center justify-between text-[10px] uppercase tracking-[0.14em] text-slate-500">
            <span>Flight Telemetry</span>
            <span className="flex items-center gap-1"><Gauge className="h-3.5 w-3.5" />Core</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <MetricCard
              label="Tracks"
              value={String(telemetry?.tracks.length ?? 0)}
              tone={telemetry?.tracks.length ? "ok" : "warn"}
              className="p-2"
            />
            <MetricCard
              label="CPU"
              value={fmt(snapshot?.cpu_percent_inst, 1, "%")}
              tone={(snapshot?.cpu_percent_inst ?? 0) >= 88 ? "warn" : "default"}
              className="p-2"
            />
            <MetricCard
              label="Battery Proxy"
              value={fmt(snapshot?.mem_percent_inst, 1, "%")}
              detail="memory saturation"
              tone={(snapshot?.mem_percent_inst ?? 0) >= 92 ? "warn" : "default"}
              className="p-2"
            />
          </div>
        </div>

        {onModelSwitch && onTrackerSwitch && (
          <div className="border-t border-slate-700/70 pt-4">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">Detection & Tracking</div>
            <ModelTrackerSelector
              activeModel={activeModel}
              activeTracker={activeTracker}
              onModelSwitch={onModelSwitch}
              onTrackerSwitch={onTrackerSwitch}
              isLoading={isModelSwitching}
              isTrackerLoading={isTrackerSwitching}
            />
          </div>
        )}

        {onExport && (
          <div className="border-t border-slate-700/70 pt-4">
            <div className="mb-2 flex items-center justify-between">
              <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">Metrics Recording</div>
              <StatusBadge tone="info">Quick Actions</StatusBadge>
            </div>
            <div className="space-y-3">
              <div className="rounded-md border border-slate-700/70 bg-slate-900/60 p-2.5">
                <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  Local Data Snapshot
                </div>
                <Button
                  size="sm"
                  onClick={onExport}
                  className="w-full justify-start border-sky-500/40 bg-sky-500/10 text-sky-100 hover:bg-sky-500/20"
                >
                  <Download className="mr-2 h-3.5 w-3.5" />
                  Export Metrics CSV
                </Button>
              </div>
              {controlStatus && (
                <div className="rounded-md border border-slate-700/70 bg-slate-900/40 px-2.5 py-2 font-mono text-[11px] text-slate-400">
                  {controlStatus}
                </div>
              )}
            </div>
          </div>
        )}
      </PanelShell>
    </aside>
  );
}
