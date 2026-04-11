import { Circle, Download, Square, Trash2, Wifi, WifiOff } from "lucide-react";
import { PanelShell } from "@/components/dashboard/PanelShell";
import { StatusBadge } from "@/components/dashboard/StatusBadge";
import { ModelTrackerSelector } from "@/components/dashboard/ModelTrackerSelector";
import { Button } from "@/components/ui/button";
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
  onStartRecording?: () => void;
  onStopRecording?: () => void;
  isRecording?: boolean;
  recordedCount?: number;
  onCloseSidebar?: () => void;
  isModelSwitching?: boolean;
  isTrackerSwitching?: boolean;
  controlStatus?: string;
  isLinkUp?: boolean;
  recordings?: Array<{
    id: string;
    createdAtIso: string;
    model: DashboardModel;
    tracker: DashboardTracker;
    sampleCount: number;
  }>;
  onDownloadRecording?: (id: string) => void;
  onDeleteRecording?: (id: string) => void;
}

export function StatusPanel({
  status,
  mode: _mode,
  telemetry,
  snapshot: _snapshot,
  activeModel = "yolov6n",
  activeTracker = "sort",
  onModelSwitch,
  onTrackerSwitch,
  onStartRecording,
  onStopRecording,
  isRecording = false,
  recordedCount = 0,
  onCloseSidebar: _onCloseSidebar,
  isModelSwitching = false,
  isTrackerSwitching = false,
  controlStatus,
  isLinkUp,
  recordings = [],
  onDownloadRecording,
  onDeleteRecording,
}: StatusPanelProps) {
  const hasTelemetry = Boolean(telemetry);
  const statusLower = status.toLowerCase();
  const explicitlyDisconnected = /(disconnected|retry|error|fail|closed|closing|connecting)/.test(statusLower);
  const explicitlyConnected = /(connected|live|open)/.test(statusLower);
  const computedHealthy = hasTelemetry || (explicitlyConnected && !explicitlyDisconnected);
  const isHealthy = isLinkUp ?? computedHealthy;

  return (
    <aside className="h-full">
      <PanelShell
        title="Operations Panel"
        className="flex h-full flex-col"
        contentClassName="flex h-full min-h-0 flex-col gap-5"
      >
        <div className="rounded-md border border-zinc-700/70 bg-zinc-900/45 p-2.5">
          <div className="flex items-center justify-between gap-2" title={status}>
            <div className="flex items-center gap-2 text-sm font-medium text-zinc-200">
              {isHealthy ? (
                <Wifi className="h-4.5 w-4.5 text-emerald-300" />
              ) : (
                <WifiOff className="h-4.5 w-4.5 text-red-300" />
              )}
              <span>{isHealthy ? "Connected" : "Disconnected"}</span>
            </div>
            <StatusBadge tone={isHealthy ? "ok" : "error"}>{isHealthy ? "Link Up" : "Link Down"}</StatusBadge>
          </div>
        </div>

        {onModelSwitch && onTrackerSwitch && (
          <div className="border-t border-zinc-700/70 pt-4">
            <div className="mb-2 flex items-center text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">Detection & Tracking</div>
            <ModelTrackerSelector
              activeModel={activeModel}
              activeTracker={activeTracker}
              onModelSwitch={onModelSwitch}
              onTrackerSwitch={onTrackerSwitch}
              isLoading={isModelSwitching}
              isTrackerLoading={isTrackerSwitching}
              disabled={!isHealthy}
            />
          </div>
        )}

        {onStartRecording && onStopRecording && (
          <div className="flex min-h-0 flex-1 flex-col border-t border-zinc-700/70 pt-4">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">Metrics Recording</div>
              <StatusBadge tone={isRecording ? "warn" : "info"}>{isRecording ? "Recording" : "Idle"}</StatusBadge>
            </div>
            <div className="flex min-h-0 flex-1 flex-col gap-3">
              <div className="rounded-md border border-zinc-700/70 bg-zinc-900/60 p-2.5">
                <div className="mb-2 flex items-center text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">
                  Session Controls
                </div>
                <Button
                  size="sm"
                  disabled={!isHealthy && !isRecording}
                  onClick={isRecording ? onStopRecording : onStartRecording}
                  className={isRecording ? "mb-2 w-full justify-start border-red-500/40 bg-red-500/10 text-red-100 hover:bg-red-500/20" : "mb-2 w-full justify-start border-emerald-500/40 bg-emerald-500/10 text-emerald-100 hover:bg-emerald-500/20"}
                >
                  {isRecording ? <Square className="mr-2 h-3.5 w-3.5" /> : <Circle className="mr-2 h-3.5 w-3.5" />}
                  {isRecording ? "Stop Recording" : "Start Recording"}
                </Button>
                <div className="mt-2 flex items-center text-[10px] text-zinc-500">Recorded samples: {recordedCount}</div>
              </div>

              <div className="flex min-h-0 flex-1 flex-col rounded-md border border-zinc-700/70 bg-zinc-900/50 p-2.5">
                <div className="mb-2 flex items-center text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">
                  Saved Recordings
                </div>
                <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border border-zinc-700/70 bg-zinc-900/55">
                  <div className="grid grid-cols-[1.2fr_1fr_1fr_1.3fr] items-center gap-2 border-b border-zinc-700/70 px-2 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-500">
                    <span className="flex items-center pl-1">Time</span>
                    <span className="flex items-center border-l border-zinc-700/60 pl-2">Model</span>
                    <span className="flex items-center border-l border-zinc-700/60 pl-2">Tracker</span>
                    <span className="flex items-center justify-center border-l border-zinc-700/60 pl-2">Actions</span>
                  </div>

                  {recordings.length === 0 ? (
                    <div className="flex flex-1 flex-col justify-start space-y-1 p-2">
                      {Array.from({ length: 4 }).map((_, index) => (
                        <div key={`placeholder-${index}`} className="grid grid-cols-[1.2fr_1fr_1fr_1.3fr] items-center gap-2 rounded-md px-1.5 py-1 text-[11px] text-zinc-500">
                          <span className="flex items-center">--:--</span>
                          <span className="flex items-center border-l border-zinc-700/50 pl-2">---</span>
                          <span className="flex items-center border-l border-zinc-700/50 pl-2">---</span>
                          <div className="flex items-center justify-center gap-1 border-l border-zinc-700/50 pl-2">
                            <button type="button" className="inline-flex h-6 w-7 items-center justify-center rounded-md border border-zinc-700/70 text-zinc-600" disabled>
                              <Download className="h-3 w-3" />
                            </button>
                            <button type="button" className="inline-flex h-6 w-7 items-center justify-center rounded-md border border-zinc-700/70 text-zinc-600" disabled>
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex-1 space-y-1 overflow-y-auto p-2">
                      {recordings.map((entry) => (
                        <div key={entry.id} className="grid grid-cols-[1.2fr_1fr_1fr_1.3fr] items-center gap-2 rounded-md border border-zinc-700/70 bg-zinc-900/70 px-1.5 py-1 text-[11px]">
                          <span className="flex items-center text-zinc-200">{new Date(entry.createdAtIso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                          <span className="truncate border-l border-zinc-700/50 pl-2 text-zinc-300">{entry.model.toUpperCase()}</span>
                          <span className="truncate border-l border-zinc-700/50 pl-2 text-zinc-300">{entry.tracker.toUpperCase()}</span>
                          <div className="flex items-center justify-center gap-1 border-l border-zinc-700/50 pl-2">
                            <Button
                              size="sm"
                              onClick={() => onDownloadRecording?.(entry.id)}
                              className="h-6 justify-center border-zinc-500/60 bg-zinc-700/35 px-2 text-zinc-100 hover:bg-zinc-700/50"
                              title="Download this recording"
                            >
                              <Download className="h-3 w-3" />
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => onDeleteRecording?.(entry.id)}
                              className="h-6 justify-center border-red-500/45 bg-red-500/10 px-2 text-red-200 hover:bg-red-500/20"
                              title="Delete this recording"
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

            </div>
          </div>
        )}
      </PanelShell>
    </aside>
  );
}
