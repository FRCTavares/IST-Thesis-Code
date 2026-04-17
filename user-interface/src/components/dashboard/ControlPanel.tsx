import { Crosshair, Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PanelShell } from "@/components/dashboard/PanelShell";
import { StatusBadge } from "@/components/dashboard/StatusBadge";
import type { DashboardModel, DashboardTracker } from "@/types/dashboard";

interface ControlPanelProps {
  activeModel: DashboardModel;
  activeTracker: DashboardTracker;
  onModelSwitch: (model: DashboardModel) => Promise<void>;
  onTrackerSwitch: (tracker: DashboardTracker) => Promise<void>;
  onTargetFocus?: (target: number | null) => Promise<void>;
  availableTrackIds?: number[];
  currentTargetId?: number | null;
  isModelSwitching?: boolean;
  isTrackerSwitching?: boolean;
  controlStatus: string;
  isLinkUp?: boolean;
  currentResolutionLabel?: string;
}

export function ControlPanel({
  activeModel,
  activeTracker,
  onModelSwitch,
  onTrackerSwitch,
  onTargetFocus,
  availableTrackIds = [],
  currentTargetId = null,
  isModelSwitching = false,
  isTrackerSwitching = false,
  controlStatus,
  isLinkUp = true,
  currentResolutionLabel,
}: ControlPanelProps) {
  const models: DashboardModel[] = ["yolov6n", "yolov8s", "yolov8m"];
  const trackers: DashboardTracker[] = ["sort", "ocsort", "bytetrack"];
  const isBusy = isModelSwitching || isTrackerSwitching;

  return (
    <PanelShell title="Control Workspace" className="flex h-full flex-col" contentClassName="flex h-full min-h-0 flex-col gap-3">
      <div className="rounded-md border border-zinc-700/80 bg-zinc-900/45 p-2.5">
        <div className="mb-2 flex items-center justify-between text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">
          <span className="flex items-center gap-1.5"><Settings2 className="h-3.5 w-3.5" />Active Configuration</span>
          <StatusBadge tone={!isLinkUp ? "error" : isBusy ? "warn" : "ok"}>{!isLinkUp ? "Link Down" : isBusy ? "Applying" : "Ready"}</StatusBadge>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge tone="info">MODEL {activeModel.toUpperCase()}</StatusBadge>
          <StatusBadge tone="info">TRACKER {activeTracker.toUpperCase()}</StatusBadge>
          <StatusBadge tone="neutral">INFER {currentResolutionLabel ?? "Unknown"}</StatusBadge>
          <StatusBadge tone={currentTargetId !== null ? "ok" : "neutral"}>TARGET {currentTargetId !== null ? `#${currentTargetId}` : "AUTO"}</StatusBadge>
        </div>
      </div>

      <div className="grid flex-1 min-h-0 content-start gap-3">
        <div className="rounded-md border border-zinc-700/80 bg-zinc-900/45 p-2.5">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Detection Model</div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {models.map((model) => (
              <Button
                key={model}
                variant={activeModel === model ? "active" : "default"}
                size="default"
                disabled={isBusy || !isLinkUp}
                onClick={() => onModelSwitch(model)}
                className="h-10 justify-center"
              >
                {model.toUpperCase()}
              </Button>
            ))}
          </div>
        </div>

        <div className="rounded-md border border-zinc-700/80 bg-zinc-900/45 p-2.5">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Tracker Backend</div>
          <div className="grid grid-cols-3 gap-2">
            {trackers.map((tracker) => (
              <Button
                key={tracker}
                variant={activeTracker === tracker ? "active" : "default"}
                size="sm"
                disabled={isBusy || !isLinkUp}
                onClick={() => onTrackerSwitch(tracker)}
                className="h-9 justify-center"
              >
                {tracker.toUpperCase()}
              </Button>
            ))}
          </div>
        </div>

        <div className="flex min-h-0 flex-col rounded-md border border-zinc-700/80 bg-zinc-900/45 p-2.5">
          <div className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">
            <Crosshair className="h-3.5 w-3.5" />
            Focus Target ID
          </div>

          <div className="mb-2 flex flex-wrap gap-2">
            <Button
              size="sm"
              variant={currentTargetId === null ? "active" : "default"}
              disabled={!isLinkUp || !onTargetFocus}
              onClick={() => onTargetFocus?.(null)}
            >
              AUTO
            </Button>
            {availableTrackIds.map((id) => (
              <Button
                key={id}
                size="sm"
                variant={currentTargetId === id ? "active" : "default"}
                disabled={!isLinkUp || !onTargetFocus}
                onClick={() => onTargetFocus?.(id)}
              >
                #{id}
              </Button>
            ))}
          </div>

          <select
            value={currentTargetId ?? "auto"}
            onChange={(e) => {
              const value = e.target.value;
              onTargetFocus?.(value === "auto" ? null : Number(value));
            }}
            disabled={!isLinkUp || !onTargetFocus}
            className="mb-2 w-full rounded-md border border-zinc-700 bg-zinc-950/80 px-3 py-2 text-sm text-zinc-100 transition-all disabled:cursor-not-allowed disabled:opacity-55 focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500"
          >
            <option value="auto">AUTO (no locked target)</option>
            {availableTrackIds.map((id) => (
              <option key={id} value={id}>
                Focus track #{id}
              </option>
            ))}
          </select>

          <div className="rounded-md border border-zinc-700/70 bg-zinc-900/60 px-2.5 py-2 text-[11px] text-zinc-400">
            {availableTrackIds.length > 0
              ? `Available targets: ${availableTrackIds.map((id) => `#${id}`).join(", ")}`
              : "No active IDs available yet."}
          </div>
        </div>
      </div>

      <div className="rounded-md border border-zinc-700/80 bg-zinc-900/55 p-2.5">
        <div className="mb-1 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">
          <Settings2 className="h-3.5 w-3.5" />
          Control Status
        </div>
        <div className="font-mono text-[11px] text-zinc-300">{controlStatus}</div>
      </div>
    </PanelShell>
  );
}
