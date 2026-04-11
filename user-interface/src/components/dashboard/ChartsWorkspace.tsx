import { useMemo, useState } from "react";
import type { MetricsSnapshot } from "@/types/dashboard";
import { PanelShell } from "@/components/dashboard/PanelShell";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface ChartsWorkspaceProps {
  samples: MetricsSnapshot[];
}

type ChartRange = "1m" | "5m" | "15m" | "all";

function formatTimeLabel(timestampIso: string): string {
  const date = new Date(timestampIso);
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  const ss = String(date.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

export function ChartsWorkspace({ samples }: ChartsWorkspaceProps) {
  const [range, setRange] = useState<ChartRange>("5m");
  const [smooth, setSmooth] = useState(true);
  const [showLegend, setShowLegend] = useState(true);
  const [showLatency, setShowLatency] = useState(true);
  const [showReplay, setShowReplay] = useState(true);
  const [showTemp, setShowTemp] = useState(true);

  const rangeLimits: Record<Exclude<ChartRange, "all">, number> = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
  };

  const rawData = useMemo(() => {
    const windowed = range === "all" ? samples.slice(-1800) : samples.slice(-rangeLimits[range]);
    return windowed.map((sample) => ({
      t: formatTimeLabel(sample.timestamp_iso),
      videoFps: sample.video_fps_10s ?? sample.video_fps_inst,
      detFps: sample.det_fps_10s ?? sample.det_fps_inst,
      latencyMs: sample.latency_ms_inst,
      detectionsNow: sample.detections_now,
      detectionsAvg: sample.detections_10s_avg,
      replayProgress: sample.replay_progress,
      cpuPct: sample.cpu_percent_10s_avg ?? sample.cpu_percent_inst,
      memPct: sample.mem_percent_10s_avg ?? sample.mem_percent_inst,
      tempC: sample.temp_c_10s_avg ?? sample.temp_c_inst,
    }));
  }, [range, samples]);

  const chartData = useMemo(() => {
    if (!smooth || rawData.length < 5) {
      return rawData;
    }

    const keys = [
      "videoFps",
      "detFps",
      "latencyMs",
      "detectionsNow",
      "detectionsAvg",
      "replayProgress",
      "cpuPct",
      "memPct",
      "tempC",
    ] as const;

    const averaged = rawData.map((entry, index) => {
      const from = Math.max(0, index - 4);
      const segment = rawData.slice(from, index + 1);
      const next = { ...entry };
      keys.forEach((key) => {
        const values = segment.map((item) => item[key]).filter((value): value is number => typeof value === "number");
        next[key] = values.length > 0 ? values.reduce((acc, value) => acc + value, 0) / values.length : null;
      });
      return next;
    });

    return averaged;
  }, [rawData, smooth]);

  const hasData = chartData.length >= 2;
  const last = chartData[chartData.length - 1];

  const summary = [
    { label: "Samples", value: String(chartData.length) },
    { label: "Video FPS", value: last?.videoFps != null ? String(Math.round(last.videoFps * 10) / 10) : "--" },
    { label: "Latency", value: last?.latencyMs != null ? `${Math.round(last.latencyMs)} ms` : "--" },
    { label: "CPU", value: last?.cpuPct != null ? `${Math.round(last.cpuPct)}%` : "--" },
  ];

  return (
    <section className="grid gap-3">
      <PanelShell title="Chart Controls" action={<div className="text-[11px] text-zinc-400">{chartData.length} samples</div>} contentClassName="grid gap-3 p-3">
        <div className="flex flex-wrap gap-2">
          {(["1m", "5m", "15m", "all"] as ChartRange[]).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setRange(option)}
              className={`h-8 rounded-md border px-3 text-xs font-semibold uppercase tracking-[0.12em] transition-all ${range === option
                ? "border-zinc-500 bg-zinc-700/50 text-zinc-100"
                : "border-zinc-700 bg-zinc-900/70 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
                }`}
            >
              {option}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setSmooth((prev) => !prev)}
            className={`h-8 rounded-md border px-3 text-xs transition-all ${smooth
              ? "border-zinc-500 bg-zinc-700/50 text-zinc-100"
              : "border-zinc-700 bg-zinc-900/70 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
              }`}
          >
            Smooth {smooth ? "On" : "Off"}
          </button>
          <button
            type="button"
            onClick={() => setShowLegend((prev) => !prev)}
            className={`h-8 rounded-md border px-3 text-xs transition-all ${showLegend
              ? "border-zinc-500 bg-zinc-700/50 text-zinc-100"
              : "border-zinc-700 bg-zinc-900/70 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
              }`}
          >
            Legend {showLegend ? "On" : "Off"}
          </button>
          <button
            type="button"
            onClick={() => setShowLatency((prev) => !prev)}
            className={`h-8 rounded-md border px-3 text-xs transition-all ${showLatency
              ? "border-zinc-500 bg-zinc-700/50 text-zinc-100"
              : "border-zinc-700 bg-zinc-900/70 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
              }`}
          >
            Latency {showLatency ? "On" : "Off"}
          </button>
          <button
            type="button"
            onClick={() => setShowReplay((prev) => !prev)}
            className={`h-8 rounded-md border px-3 text-xs transition-all ${showReplay
              ? "border-zinc-500 bg-zinc-700/50 text-zinc-100"
              : "border-zinc-700 bg-zinc-900/70 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
              }`}
          >
            Replay {showReplay ? "On" : "Off"}
          </button>
          <button
            type="button"
            onClick={() => setShowTemp((prev) => !prev)}
            className={`h-8 rounded-md border px-3 text-xs transition-all ${showTemp
              ? "border-zinc-500 bg-zinc-700/50 text-zinc-100"
              : "border-zinc-700 bg-zinc-900/70 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
              }`}
          >
            Temp {showTemp ? "On" : "Off"}
          </button>
        </div>
      </PanelShell>

      <PanelShell title="Chart Overview" contentClassName="p-3">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {summary.map((item) => (
            <div key={item.label} className="rounded-md border border-zinc-700/80 bg-zinc-900/55 px-2.5 py-2">
              <div className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">{item.label}</div>
              <div className="mt-1 text-lg font-semibold text-zinc-100">{item.value}</div>
            </div>
          ))}
        </div>
      </PanelShell>

      {!hasData ? (
        <PanelShell title="Charts" contentClassName="p-3">
          <div className="flex h-[420px] items-center justify-center rounded-md border border-zinc-700/70 bg-zinc-900/55">
            <div className="text-center">
              <div className="text-sm font-medium text-zinc-200">Waiting for telemetry samples</div>
              <div className="mt-1 text-xs text-zinc-500">Need at least 2 samples in the selected range to render charts.</div>
            </div>
          </div>
        </PanelShell>
      ) : (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          <PanelShell title="FPS and Latency" contentClassName="p-2">
            <div className="h-[300px] w-full rounded-md border border-zinc-700/70 bg-zinc-900/65 p-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid stroke="#3f3f46" strokeDasharray="2 4" vertical={false} />
                  <XAxis dataKey="t" minTickGap={28} tick={{ fill: "#71717a", fontSize: 10 }} />
                  <YAxis yAxisId="left" width={36} tick={{ fill: "#71717a", fontSize: 10 }} stroke="#a1a1aa" />
                  <YAxis yAxisId="right" orientation="right" width={40} tick={{ fill: "#71717a", fontSize: 10 }} stroke="#f59e0b" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "rgba(24, 24, 27, 0.95)",
                      border: "1px solid rgba(82, 82, 91, 0.8)",
                      borderRadius: "8px",
                      color: "#d4d4d8",
                    }}
                  />
                  {showLegend && <Legend wrapperStyle={{ color: "#a1a1aa", fontSize: "11px" }} />}
                  <Line yAxisId="left" type="monotone" dataKey="videoFps" stroke="#d4d4d8" dot={false} strokeWidth={1.8} name="Video FPS" />
                  <Line yAxisId="left" type="monotone" dataKey="detFps" stroke="#a1a1aa" dot={false} strokeWidth={1.8} name="Detection FPS" />
                  {showLatency && <Line yAxisId="right" type="monotone" dataKey="latencyMs" stroke="#f59e0b" dot={false} strokeWidth={1.8} name="Latency ms" />}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </PanelShell>

          <PanelShell title="Detections and Replay" contentClassName="p-2">
            <div className="h-[300px] w-full rounded-md border border-zinc-700/70 bg-zinc-900/65 p-2">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <CartesianGrid stroke="#3f3f46" strokeDasharray="2 4" vertical={false} />
                  <XAxis dataKey="t" minTickGap={28} tick={{ fill: "#71717a", fontSize: 10 }} />
                  <YAxis yAxisId="left" width={36} tick={{ fill: "#71717a", fontSize: 10 }} stroke="#a1a1aa" />
                  <YAxis yAxisId="right" orientation="right" width={40} tick={{ fill: "#71717a", fontSize: 10 }} stroke="#f59e0b" domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "rgba(24, 24, 27, 0.95)",
                      border: "1px solid rgba(82, 82, 91, 0.8)",
                      borderRadius: "8px",
                      color: "#d4d4d8",
                    }}
                  />
                  {showLegend && <Legend wrapperStyle={{ color: "#a1a1aa", fontSize: "11px" }} />}
                  <Area yAxisId="left" type="monotone" dataKey="detectionsNow" stroke="#d4d4d8" fill="#3f3f46" fillOpacity={0.35} name="Detections Now" />
                  <Line yAxisId="left" type="monotone" dataKey="detectionsAvg" stroke="#a1a1aa" dot={false} strokeWidth={1.8} name="Detections Avg 10s" />
                  {showReplay && <Line yAxisId="right" type="monotone" dataKey="replayProgress" stroke="#f59e0b" dot={false} strokeWidth={1.8} name="Replay %" />}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </PanelShell>

          <PanelShell title="System Load" className="xl:col-span-2" contentClassName="p-2">
            <div className="h-[300px] w-full rounded-md border border-zinc-700/70 bg-zinc-900/65 p-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid stroke="#3f3f46" strokeDasharray="2 4" vertical={false} />
                  <XAxis dataKey="t" minTickGap={28} tick={{ fill: "#71717a", fontSize: 10 }} />
                  <YAxis yAxisId="left" width={40} tick={{ fill: "#71717a", fontSize: 10 }} stroke="#a1a1aa" domain={[0, 100]} />
                  <YAxis yAxisId="right" orientation="right" width={40} tick={{ fill: "#71717a", fontSize: 10 }} stroke="#f59e0b" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "rgba(24, 24, 27, 0.95)",
                      border: "1px solid rgba(82, 82, 91, 0.8)",
                      borderRadius: "8px",
                      color: "#d4d4d8",
                    }}
                  />
                  {showLegend && <Legend wrapperStyle={{ color: "#a1a1aa", fontSize: "11px" }} />}
                  <Line yAxisId="left" type="monotone" dataKey="cpuPct" stroke="#d4d4d8" dot={false} strokeWidth={1.8} name="CPU %" />
                  <Line yAxisId="left" type="monotone" dataKey="memPct" stroke="#a1a1aa" dot={false} strokeWidth={1.8} name="Memory %" />
                  {showTemp && <Line yAxisId="right" type="monotone" dataKey="tempC" stroke="#f59e0b" dot={false} strokeWidth={1.8} name="Temp C" />}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </PanelShell>
        </div>
      )}
    </section>
  );
}
