import type { MetricsSnapshot } from "@/types/dashboard";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PanelShell } from "@/components/dashboard/PanelShell";

interface PerformanceChartProps {
  samples: MetricsSnapshot[];
}

export function PerformanceChart({ samples }: PerformanceChartProps) {
  const data = samples.slice(-50).map((sample, index) => ({
    i: index,
    videoFps: sample.video_fps_10s ?? sample.video_fps_inst,
    detFps: sample.det_fps_10s ?? sample.det_fps_inst,
    latency: sample.latency_ms_inst,
  }));

  return (
    <PanelShell title="Performance Trends" contentClassName="p-2">
      <div className="h-56 w-full rounded-md border border-slate-700/70 bg-slate-900/65 p-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid stroke="#334155" strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="i" hide stroke="#64748b" />
            <YAxis yAxisId="left" width={32} stroke="#60a5fa" tick={{ fill: "#64748b", fontSize: 10 }} />
            <YAxis
              yAxisId="right"
              orientation="right"
              width={32}
              stroke="#f59e0b"
              tick={{ fill: "#64748b", fontSize: 10 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgba(15, 23, 42, 0.95)",
                border: "1px solid rgba(71, 85, 105, 0.8)",
                borderRadius: "8px",
                color: "#cbd5e1",
              }}
            />
            <Legend wrapperStyle={{ color: "#94a3b8", fontSize: "11px" }} />
            <Line yAxisId="left" type="monotone" dataKey="videoFps" stroke="#3b82f6" dot={false} strokeWidth={1.7} name="Video FPS" />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="detFps"
              stroke="#60a5fa"
              dot={false}
              strokeWidth={1.7}
              name="Detection FPS"
            />
            <Line yAxisId="right" type="monotone" dataKey="latency" stroke="#f59e0b" dot={false} strokeWidth={1.7} name="Latency ms" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </PanelShell>
  );
}
