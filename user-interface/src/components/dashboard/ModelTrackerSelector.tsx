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
    disabled?: boolean;
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
    disabled = false,
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
            <div className="rounded-md border border-zinc-700/70 bg-zinc-900/45 px-2.5 py-2">
                <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.12em] text-zinc-500">
                    <span className="inline-flex items-center leading-none">Active</span>
                    <span className="inline-flex h-5 items-center rounded-full border border-zinc-500/60 bg-zinc-700/35 px-2 font-semibold leading-none text-zinc-200">
                        MODEL {activeModel.toUpperCase()}
                    </span>
                    <span className="inline-flex h-5 items-center rounded-full border border-zinc-500/60 bg-zinc-700/35 px-2 font-semibold leading-none text-zinc-200">
                        TRACKER {activeTracker.toUpperCase()}
                    </span>
                </div>
            </div>

            <div className="space-y-2 rounded-md border border-zinc-700/70 bg-zinc-900/35 p-2.5">
                <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
                    Detection Model
                </label>
                <select
                    value={selectedModel}
                    onChange={(e) => handleModelChange(e.target.value as DashboardModel)}
                    disabled={disabled || isBusy || isLoading}
                    className="w-full rounded-md border border-zinc-700 bg-zinc-950/80 px-3 py-2 text-sm text-zinc-100 transition-all disabled:cursor-not-allowed disabled:opacity-55 focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500"
                >
                    {MODELS.map((model) => (
                        <option key={model} value={model}>
                            {model.toUpperCase()}
                        </option>
                    ))}
                </select>
            </div>

            <div className="space-y-2 rounded-md border border-zinc-700/70 bg-zinc-900/35 p-2.5">
                <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
                    Tracker Backend
                </label>
                <select
                    value={selectedTracker}
                    onChange={(e) => handleTrackerChange(e.target.value as DashboardTracker)}
                    disabled={disabled || isBusy || isTrackerLoading}
                    className="w-full rounded-md border border-zinc-700 bg-zinc-950/80 px-3 py-2 text-sm text-zinc-100 transition-all disabled:cursor-not-allowed disabled:opacity-55 focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500"
                >
                    {TRACKERS.map((tracker) => (
                        <option key={tracker} value={tracker}>
                            {tracker.toUpperCase()}
                        </option>
                    ))}
                </select>
            </div>

            {isBusy && (
                <div className="rounded-md border border-amber-500/35 bg-amber-500/8 px-2.5 py-2 text-[11px] text-amber-200">
                    Applying changes. Telemetry may briefly fluctuate during reconfiguration.
                </div>
            )}

            {statusMessage && (
                <div className="rounded-md border border-zinc-700/50 bg-zinc-900/50 px-2 py-1.5 text-[11px] text-zinc-400">
                    {statusMessage}
                </div>
            )}
        </div>
    );
}
