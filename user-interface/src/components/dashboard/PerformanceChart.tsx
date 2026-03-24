import type { MetricsSnapshot } from "@/types/dashboard";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";

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
    <div className="h-52 w-full rounded-lg border border-border bg-slate-50 p-2">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <XAxis dataKey="i" hide />
          <YAxis yAxisId="left" stroke="#0f766e" />
          <YAxis yAxisId="right" orientation="right" stroke="#be123c" />
          <Tooltip />
          <Legend />
          <Line yAxisId="left" type="monotone" dataKey="videoFps" stroke="#0ea5a4" dot={false} name="Video FPS" />
          <Line yAxisId="left" type="monotone" dataKey="detFps" stroke="#0369a1" dot={false} name="Detection FPS" />
          <Line yAxisId="right" type="monotone" dataKey="latency" stroke="#be123c" dot={false} name="Latency ms" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
