import type { MetricsSnapshot } from "@/types/dashboard";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PanelShell } from "@/components/dashboard/PanelShell";

interface PerformanceChartProps {
  samples: MetricsSnapshot[];
}

export function PerformanceChart({ samples }: PerformanceChartProps) {
  const data = samples.slice(-50).map((sample, index) => ({
    i: index,
    cameraInputFps: sample.camera_input_fps_roll ?? sample.camera_input_fps_inst,
    detOutFps: sample.det_out_fps_roll ?? sample.det_out_fps_inst,
    e2eDetMs: sample.e2e_det_ms_inst,
  }));

  return (
    <PanelShell title="Performance Trends" contentClassName="p-2">
      <div className="h-56 w-full rounded-md border border-zinc-700/70 bg-zinc-900/65 p-2">
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
            <Line yAxisId="left" type="monotone" dataKey="cameraInputFps" stroke="#3b82f6" dot={false} strokeWidth={1.7} name="Camera Input FPS" />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="detOutFps"
              stroke="#60a5fa"
              dot={false}
              strokeWidth={1.7}
              name="Detection Output FPS"
            />
            <Line yAxisId="right" type="monotone" dataKey="e2eDetMs" stroke="#f59e0b" dot={false} strokeWidth={1.7} name="Detection E2E ms" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </PanelShell>
  );
}
