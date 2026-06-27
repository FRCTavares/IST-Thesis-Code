import type { MetricsSnapshot } from "@/types/dashboard";

export function exportMetricsCsv(samples: MetricsSnapshot[], model: string): void {
  if (!samples.length) {
    return;
  }

  const headers = [
    "timestamp_iso",
    "model",
    "metrics_schema_version",
    "health_score",
    "camera_input_fps_inst",
    "camera_input_fps_roll",
    "det_out_fps_inst",
    "det_out_fps_roll",
    "e2e_det_ms_inst",
    "e2e_det_p50_ms",
    "e2e_det_p95_ms",
    "pub_dt_warn_ms",
    "pub_dt_ms_inst",
    "pub_dt_p95_ms",
    "replay_progress",
    "detections_now",
    "detections_10s_avg",
    "detections_10s_max",
    "cpu_percent_inst",
    "cpu_percent_10s_avg",
    "mem_percent_inst",
    "mem_percent_10s_avg",
    "mem_used_mb_inst",
    "temp_c_inst",
    "temp_c_10s_avg",
  ] as const;

  const rows = [headers.join(",")];
  for (const sample of samples) {
    rows.push(headers.map((header) => toCsvCell(sample[header])).join(","));
  }

  const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  const stamp = new Date().toISOString().replace(/[:]/g, "-").replace(/\..+$/, "");
  const filename = `dashboard_metrics_${model}_${stamp}.csv`;

  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();

  URL.revokeObjectURL(url);
}

function toCsvCell(value: unknown): string {
  const str = value === null || value === undefined ? "" : String(value);
  if (str.includes(",") || str.includes("\"") || str.includes("\n")) {
    return `"${str.replace(/\"/g, '""')}"`;
  }
  return str;
}
