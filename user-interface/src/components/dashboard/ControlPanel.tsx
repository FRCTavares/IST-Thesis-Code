import { Activity, Circle, Download, Server, Settings2, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PanelShell } from "@/components/dashboard/PanelShell";
import { StatusBadge } from "@/components/dashboard/StatusBadge";
import type { DashboardModel, DashboardTracker } from "@/types/dashboard";

interface ControlPanelProps {
  activeModel: DashboardModel;
  activeTracker: DashboardTracker;
  onStartRecording: () => void;
  onStopRecording: () => void;
  isRecording: boolean;
  recordedCount: number;
  canExport: boolean;
  onExport: () => void;
  onModelSwitch: (model: DashboardModel) => Promise<void>;
  onTrackerSwitch: (tracker: DashboardTracker) => Promise<void>;
  isModelSwitching?: boolean;
  isTrackerSwitching?: boolean;
  controlStatus: string;
}

export function ControlPanel({
  activeModel,
  activeTracker,
  onStartRecording,
  onStopRecording,
  isRecording,
  recordedCount,
  canExport,
  onExport,
  onModelSwitch,
  onTrackerSwitch,
  isModelSwitching = false,
  isTrackerSwitching = false,
  controlStatus,
}: ControlPanelProps) {
  const models: DashboardModel[] = ["yolov6n", "yolov8s", "yolov8m"];
  const trackers: DashboardTracker[] = ["sort", "ocsort", "bytetrack"];
  const isBusy = isModelSwitching || isTrackerSwitching;

  return (
    <PanelShell title="Control Console" className="h-full">
      <div className="grid gap-3">
        <div className="rounded-md border border-slate-700/80 bg-slate-900/45 p-2.5">
          <div className="mb-2 flex items-center justify-between text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            <span className="flex items-center gap-1.5"><Settings2 className="h-3.5 w-3.5" />Active Configuration</span>
            <StatusBadge tone={isBusy ? "warn" : "ok"}>{isBusy ? "Applying" : "Ready"}</StatusBadge>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge tone="info">MODEL {activeModel.toUpperCase()}</StatusBadge>
            <StatusBadge tone="info">TRACKER {activeTracker.toUpperCase()}</StatusBadge>
          </div>
        </div>

        <div className="rounded-md border border-slate-700/80 bg-slate-900/45 p-2.5">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Model</div>
          <div className="flex flex-wrap gap-2">
            {models.map((model) => (
              <Button
                key={model}
                variant={activeModel === model ? "active" : "default"}
                size="sm"
                disabled={isBusy}
                onClick={() => onModelSwitch(model)}
              >
                {model.toUpperCase()}
              </Button>
            ))}
          </div>
          <div className="mt-2 text-[10px] text-slate-500">
            {isModelSwitching ? "Switching model and restarting detector..." : "Detector model switch (container restart)"}
          </div>
        </div>

        <div className="rounded-md border border-slate-700/80 bg-slate-900/45 p-2.5">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Tracker</div>
          <div className="flex flex-wrap gap-2">
            {trackers.map((tracker) => (
              <Button
                key={tracker}
                variant={activeTracker === tracker ? "active" : "default"}
                size="sm"
                disabled={isBusy}
                onClick={() => onTrackerSwitch(tracker)}
              >
                {tracker.toUpperCase()}
              </Button>
            ))}
          </div>
          <div className="mt-2 text-[10px] text-slate-500">
            {isTrackerSwitching ? "Switching tracker backend..." : "Runtime tracker backend switch"}
          </div>
        </div>

        <div className="rounded-md border border-slate-700/80 bg-slate-900/45 p-2.5">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Actions</div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant={isRecording ? "danger" : "active"} onClick={isRecording ? onStopRecording : onStartRecording}>
              {isRecording ? <Square className="mr-1.5 h-3.5 w-3.5" /> : <Circle className="mr-1.5 h-3.5 w-3.5" />}
              {isRecording ? "Stop Recording" : "Start Recording"}
            </Button>
            <Button
              size="sm"
              onClick={onExport}
              disabled={!canExport}
              className={canExport ? undefined : "border-slate-700/80 bg-slate-800/60 text-slate-500"}
              title={canExport ? "Export recorded metrics to CSV" : "No recorded metrics available"}
            >
              <Download className="mr-1.5 h-3.5 w-3.5" />
              Export Metrics CSV
            </Button>
          </div>
          <div className="mt-2 text-[10px] text-slate-500">Recorded samples: {recordedCount}</div>
        </div>

        <div className="rounded-md border border-slate-700/80 bg-slate-900/55 p-2.5">
          <div className="mb-1 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            <Activity className="h-3.5 w-3.5" />
            Control Status
          </div>
          <div className="font-mono text-[11px] text-slate-300">{controlStatus}</div>
        </div>

        <div className="rounded-md border border-slate-700/80 bg-slate-900/55 p-2.5 font-mono text-[11px] text-slate-400">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <Server className="h-3.5 w-3.5" />
            Backend Contract
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge tone="info">POST /api/model</StatusBadge>
          </div>
          <div className="mt-2 text-[10px] uppercase tracking-[0.14em] text-slate-500">WS telemetry: tracks / detections / target / fps / timing / system</div>
          <div className="mt-2 flex flex-wrap gap-2">
            <StatusBadge tone="info">POST /api/tracker</StatusBadge>
          </div>
        </div>
      </div>
    </PanelShell>
  );
}
