import { Download, RefreshCw, Server } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PanelShell } from "@/components/dashboard/PanelShell";
import { StatusBadge } from "@/components/dashboard/StatusBadge";
import type { DashboardModel } from "@/types/dashboard";

interface ControlPanelProps {
  activeModel: DashboardModel;
  onReplay: () => void;
  onExport: () => void;
  onModelSwitch: (model: DashboardModel) => void;
  controlStatus: string;
}

export function ControlPanel({ activeModel, onReplay, onExport, onModelSwitch, controlStatus }: ControlPanelProps) {
  const models: DashboardModel[] = ["yolov6n", "yolov8s", "yolov8m"];

  return (
    <PanelShell title="Control Console" className="h-full">
      <div className="grid gap-3">
        <div>
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Model</div>
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

        <div>
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Actions</div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={onReplay}>
              <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
              Replay + Auto Log
            </Button>
            <Button size="sm" onClick={onExport}>
              <Download className="mr-1.5 h-3.5 w-3.5" />
              Export Metrics CSV
            </Button>
          </div>
        </div>

        <div className="rounded-md border border-slate-700/80 bg-slate-900/55 p-2.5">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Control Status</div>
          <div className="font-mono text-[11px] text-slate-300">{controlStatus}</div>
        </div>

        <div className="rounded-md border border-slate-700/80 bg-slate-900/55 p-2.5 font-mono text-[11px] text-slate-400">
          <div className="mb-2 flex items-center gap-2 text-slate-200">
            <Server className="h-3.5 w-3.5" />
            Backend Contract
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge tone="info">POST /api/model</StatusBadge>
            <StatusBadge tone="info">POST /api/replay</StatusBadge>
          </div>
          <div className="mt-2 text-[10px] uppercase tracking-[0.14em] text-slate-500">WS telemetry: tracks / detections / target / fps / timing / system</div>
        </div>
      </div>
    </PanelShell>
  );
}
