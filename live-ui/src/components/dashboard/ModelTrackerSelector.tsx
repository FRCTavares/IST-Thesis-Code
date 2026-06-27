import { useEffect, useMemo, useState } from "react";
import type { DashboardModel, DashboardTracker } from "@/types/dashboard";
import { requestTargetFocus } from "@/features/dashboard/services/dashboardApi";

type TrackLike = {
    id: number;
    label?: string;
    score?: number;
    w?: number;
    h?: number;
};

interface ModelTrackerSelectorProps {
    activeModel: DashboardModel;
    availableModels: DashboardModel[];
    activeTracker: DashboardTracker;
    onModelSwitch: (model: DashboardModel) => Promise<void>;
    onTrackerSwitch: (tracker: DashboardTracker) => Promise<void>;
    tracks?: TrackLike[];
    activeTargetId?: number | null;
    isLoading?: boolean;
    isTrackerLoading?: boolean;
    statusMessage?: string;
    disabled?: boolean;
}

const TRACKERS: DashboardTracker[] = ["sort", "ocsort", "bytetrack", "deepsort"];

export function ModelTrackerSelector({
    activeModel,
    availableModels,
    activeTracker,
    onModelSwitch,
    onTrackerSwitch,
    tracks = [],
    activeTargetId = null,
    isLoading = false,
    isTrackerLoading = false,
    statusMessage,
    disabled = false,
}: ModelTrackerSelectorProps) {
    const [selectedModel, setSelectedModel] = useState<DashboardModel>(activeModel);
    const [selectedTracker, setSelectedTracker] = useState<DashboardTracker>(activeTracker);
    const [targetBusy, setTargetBusy] = useState(false);
    const [targetMessage, setTargetMessage] = useState<string | null>(null);

    const isBusy = isLoading || isTrackerLoading;

    const personTracks = useMemo(() => {
        return [...tracks]
            .filter((track) => !track.label || track.label === "person")
            .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    }, [tracks]);

    const bestTrack = personTracks[0] ?? null;

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

    const handleTargetFocus = async (target: number | null) => {
        setTargetBusy(true);
        setTargetMessage(null);

        const response = await requestTargetFocus(target);

        setTargetBusy(false);

        if (!response.ok) {
            setTargetMessage(response.error ?? "Target selection failed");
            return;
        }

        setTargetMessage(target === null ? "Target cleared" : `Following track ${target}`);
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
                    {activeTargetId ? (
                        <span className="inline-flex h-5 items-center rounded-full border border-emerald-500/50 bg-emerald-500/15 px-2 font-semibold leading-none text-emerald-200">
                            TARGET {activeTargetId}
                        </span>
                    ) : null}
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
                    {availableModels.map((model) => (
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

            <div className="space-y-2 rounded-md border border-zinc-700/70 bg-zinc-900/35 p-2.5">
                <div className="flex items-center justify-between gap-2">
                    <div>
                        <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-zinc-400">
                            Target to Follow
                        </label>
                        <p className="mt-1 text-[11px] text-zinc-500">
                            Select a visible track without opening the control page.
                        </p>
                    </div>

                    <button
                        type="button"
                        disabled={!bestTrack || targetBusy || disabled}
                        onClick={() => bestTrack && handleTargetFocus(bestTrack.id)}
                        className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1.5 text-xs font-semibold text-emerald-200 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                        Follow Best
                    </button>
                </div>

                <div className="space-y-1.5">
                    {personTracks.length === 0 ? (
                        <div className="rounded-md border border-dashed border-zinc-700/70 px-2.5 py-2 text-xs text-zinc-500">
                            No tracks available.
                        </div>
                    ) : (
                        personTracks.slice(0, 5).map((track) => (
                            <div
                                key={track.id}
                                className="flex items-center justify-between gap-2 rounded-md bg-zinc-950/50 px-2.5 py-2"
                            >
                                <div className="min-w-0">
                                    <div className="flex items-center gap-2 text-sm font-medium text-zinc-100">
                                        Track {track.id}
                                        {activeTargetId === track.id ? (
                                            <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-emerald-200">
                                                active
                                            </span>
                                        ) : null}
                                    </div>
                                    <div className="text-[11px] text-zinc-500">
                                        score {(track.score ?? 0).toFixed(2)}
                                        {track.w && track.h ? ` · ${Math.round(track.w)}×${Math.round(track.h)}` : ""}
                                    </div>
                                </div>

                                <button
                                    type="button"
                                    disabled={targetBusy || disabled}
                                    onClick={() => handleTargetFocus(track.id)}
                                    className="rounded-md border border-zinc-700 px-2.5 py-1.5 text-xs font-semibold text-zinc-200 transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
                                >
                                    Follow
                                </button>
                            </div>
                        ))
                    )}
                </div>

                <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] text-zinc-500">{targetMessage}</span>

                    <button
                        type="button"
                        disabled={targetBusy || disabled}
                        onClick={() => handleTargetFocus(null)}
                        className="rounded-md px-2 py-1 text-[11px] text-zinc-500 transition hover:bg-zinc-800 hover:text-zinc-200 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                        Clear target
                    </button>
                </div>
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