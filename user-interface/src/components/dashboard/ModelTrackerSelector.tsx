import { useEffect, useState } from "react";
import type { DashboardModel, DashboardTracker } from "@/types/dashboard";

interface ModelTrackerSelectorProps {
    activeModel: DashboardModel;
    activeTracker: DashboardTracker;
    onModelSwitch: (model: DashboardModel) => Promise<void>;
    onTrackerSwitch: (tracker: DashboardTracker) => Promise<void>;
    isLoading?: boolean;
    isTrackerLoading?: boolean;
    statusMessage?: string;
}

const MODELS: DashboardModel[] = ["yolov6n", "yolov8s", "yolov8m"];
const TRACKERS: DashboardTracker[] = ["sort", "ocsort", "bytetrack"];

export function ModelTrackerSelector({
    activeModel,
    activeTracker,
    onModelSwitch,
    onTrackerSwitch,
    isLoading = false,
    isTrackerLoading = false,
    statusMessage,
}: ModelTrackerSelectorProps) {
    const [selectedModel, setSelectedModel] = useState<DashboardModel>(activeModel);
    const [selectedTracker, setSelectedTracker] = useState<DashboardTracker>(activeTracker);
    const isBusy = isLoading || isTrackerLoading;

    useEffect(() => {
        setSelectedModel(activeModel);
    }, [activeModel]);

    useEffect(() => {
        setSelectedTracker(activeTracker);
    }, [activeTracker]);

    const handleModelChange = async (model: DashboardModel) => {
        setSelectedModel(model);
        await onModelSwitch(model);
    };

    const handleTrackerChange = async (tracker: DashboardTracker) => {
        setSelectedTracker(tracker);
        await onTrackerSwitch(tracker);
    };

    return (
        <div className="space-y-3">
            <div className="rounded-md border border-slate-700/70 bg-slate-900/45 px-2.5 py-2">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.12em] text-slate-500">
                    <span>Active</span>
                    <span className="rounded-full border border-sky-500/40 bg-sky-500/12 px-2 py-0.5 font-semibold text-sky-200">
                        MODEL {activeModel.toUpperCase()}
                    </span>
                    <span className="rounded-full border border-emerald-500/35 bg-emerald-500/12 px-2 py-0.5 font-semibold text-emerald-200">
                        TRACKER {activeTracker.toUpperCase()}
                    </span>
                </div>
            </div>

            <div className="space-y-2 rounded-md border border-slate-700/70 bg-slate-900/35 p-2.5">
                <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                    Detection Model
                </label>
                <select
                    value={selectedModel}
                    onChange={(e) => handleModelChange(e.target.value as DashboardModel)}
                    disabled={isBusy || isLoading}
                    className="w-full rounded-md border border-slate-700 bg-slate-950/80 px-3 py-2 text-sm text-slate-100 transition-all disabled:cursor-not-allowed disabled:opacity-55 focus:border-sky-500 focus:ring-1 focus:ring-sky-500"
                >
                    {MODELS.map((model) => (
                        <option key={model} value={model}>
                            {model.toUpperCase()}
                        </option>
                    ))}
                </select>
                <div className="text-[10px] text-slate-500">
                    {isLoading ? "Switching model and restarting detector..." : "Switches the detector model (container restart)"}
                </div>
            </div>

            <div className="space-y-2 rounded-md border border-slate-700/70 bg-slate-900/35 p-2.5">
                <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                    Tracker Backend
                </label>
                <select
                    value={selectedTracker}
                    onChange={(e) => handleTrackerChange(e.target.value as DashboardTracker)}
                    disabled={isBusy || isTrackerLoading}
                    className="w-full rounded-md border border-slate-700 bg-slate-950/80 px-3 py-2 text-sm text-slate-100 transition-all disabled:cursor-not-allowed disabled:opacity-55 focus:border-sky-500 focus:ring-1 focus:ring-sky-500"
                >
                    {TRACKERS.map((tracker) => (
                        <option key={tracker} value={tracker}>
                            {tracker.toUpperCase()}
                        </option>
                    ))}
                </select>
                <div className="text-[10px] text-slate-500">
                    {isTrackerLoading ? "Switching tracker backend..." : "Switches tracker backend at runtime"}
                </div>
            </div>

            {isBusy && (
                <div className="rounded-md border border-amber-500/35 bg-amber-500/8 px-2.5 py-2 text-[11px] text-amber-200">
                    Applying changes. Telemetry may briefly fluctuate during reconfiguration.
                </div>
            )}

            {statusMessage && (
                <div className="rounded-md border border-slate-700/50 bg-slate-900/50 px-2 py-1.5 text-[11px] text-slate-400">
                    {statusMessage}
                </div>
            )}
        </div>
    );
}
