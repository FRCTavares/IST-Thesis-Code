import { RefreshCw, Download, Wifi, Server } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { DashboardDataMode, DashboardModel } from "@/types/dashboard";

interface StatusPanelProps {
  status: string;
  mode: DashboardDataMode;
  activeModel: DashboardModel;
  onReplay: () => void;
  onExport: () => void;
  onModelSwitch: (model: DashboardModel) => void;
  controlStatus: string;
}

export function StatusPanel({
  status,
  mode,
  activeModel,
  onReplay,
  onExport,
  onModelSwitch,
  controlStatus,
}: StatusPanelProps) {
  const models: DashboardModel[] = ["yolov6n", "yolov8s", "yolov8m"];

  return (
    <aside className="grid gap-3 rounded-2xl border border-border bg-card p-3 shadow-panel">
      <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
        <div className="mb-1 flex items-center gap-2 font-medium">
          <Wifi className="h-4 w-4" />
          {status}
        </div>
        <div className="font-mono text-xs">mode={mode}</div>
      </div>

      <div className="rounded-lg border border-border bg-slate-50 p-3">
        <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Model Switch</div>
        <div className="flex flex-wrap gap-2">
          {models.map((model) => (
            <Button
              key={model}
              variant={activeModel === model ? "active" : "default"}
              size="sm"
              onClick={() => onModelSwitch(model)}
            >
              {model.toUpperCase()}
            </Button>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-border bg-slate-50 p-3">
        <div className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Run Controls</div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={onReplay}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Replay + Auto Log
          </Button>
          <Button size="sm" onClick={onExport}>
            <Download className="mr-2 h-4 w-4" />
            Export Metrics CSV
          </Button>
        </div>
        <div className="mt-2 font-mono text-xs text-muted-foreground">{controlStatus}</div>
      </div>

      <div className="rounded-lg border border-border bg-slate-50 p-3 font-mono text-xs text-muted-foreground">
        <div className="mb-1 flex items-center gap-1 text-foreground">
          <Server className="h-3 w-3" />
          Backend Contract
        </div>
        <div>POST /api/model</div>
        <div>POST /api/replay</div>
        <div>WS telemetry: tracks/detections/target/fps/timing/system</div>
      </div>
    </aside>
  );
}
