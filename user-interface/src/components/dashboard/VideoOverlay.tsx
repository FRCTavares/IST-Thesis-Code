import { useEffect, useMemo, useRef, useState } from "react";
import { Crosshair, Radar } from "lucide-react";
import type { DashboardTelemetry } from "@/types/dashboard";
import { fmt } from "@/features/dashboard/utils/metrics";
import { StatusBadge } from "@/components/dashboard/StatusBadge";
import { overlayStyle } from "@/components/dashboard/OverlayBox";

interface VideoOverlayProps {
  telemetry: DashboardTelemetry | null;
  videoUrl: string;
}

interface NormalizedBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

function overlapIoU(a: NormalizedBox, b: NormalizedBox): number {
  const ax1 = a.x - a.w * 0.5;
  const ay1 = a.y - a.h * 0.5;
  const ax2 = a.x + a.w * 0.5;
  const ay2 = a.y + a.h * 0.5;

  const bx1 = b.x - b.w * 0.5;
  const by1 = b.y - b.h * 0.5;
  const bx2 = b.x + b.w * 0.5;
  const by2 = b.y + b.h * 0.5;

  const ix1 = Math.max(ax1, bx1);
  const iy1 = Math.max(ay1, by1);
  const ix2 = Math.min(ax2, bx2);
  const iy2 = Math.min(ay2, by2);

  const iw = Math.max(0, ix2 - ix1);
  const ih = Math.max(0, iy2 - iy1);
  const intersection = iw * ih;
  if (intersection <= 0) {
    return 0;
  }

  const areaA = Math.max(0, ax2 - ax1) * Math.max(0, ay2 - ay1);
  const areaB = Math.max(0, bx2 - bx1) * Math.max(0, by2 - by1);
  const union = areaA + areaB - intersection;

  return union > 0 ? intersection / union : 0;
}

export function VideoOverlay({ telemetry, videoUrl }: VideoOverlayProps) {
  const videoRef = useRef<HTMLImageElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const lastTargetBoxRef = useRef<{ x: number; y: number; w: number; h: number } | null>(null);
  const lastTargetVisibleRef = useRef(false);
  const [reacquired, setReacquired] = useState(false);

  const detections = useMemo(() => telemetry?.detections ?? [], [telemetry]);
  const targetTrack = useMemo(() => {
    if (!telemetry || telemetry.target === null || telemetry.target === undefined) {
      return null;
    }
    return telemetry.tracks.find((track) => track.id === telemetry.target) ?? null;
  }, [telemetry]);

  useEffect(() => {
    const visible = Boolean(targetTrack);
    if (visible && !lastTargetVisibleRef.current) {
      setReacquired(true);
      const timer = window.setTimeout(() => setReacquired(false), 1500);
      lastTargetVisibleRef.current = true;
      return () => window.clearTimeout(timer);
    }
    lastTargetVisibleRef.current = visible;
    return undefined;
  }, [targetTrack]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) {
      return;
    }

    const resize = () => {
      const rect = video.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(rect.width));
      canvas.height = Math.max(1, Math.floor(rect.height));
      draw();
    };

    const draw = () => {
      const context = canvas.getContext("2d");
      if (!context) {
        return;
      }

      context.clearRect(0, 0, canvas.width, canvas.height);

      const imgW = Math.max(1, video.naturalWidth || canvas.width);
      const imgH = Math.max(1, video.naturalHeight || canvas.height);
      const scale = Math.min(canvas.width / imgW, canvas.height / imgH);
      const drawW = imgW * scale;
      const drawH = imgH * scale;
      const offX = 0.5 * (canvas.width - drawW);
      const offY = 0.5 * (canvas.height - drawH);

      const displayDetections =
        targetTrack === null
          ? detections
          : detections.filter((det) => overlapIoU(det, targetTrack) < 0.55);

      displayDetections.forEach((det) => {
        const x = offX + (det.x - 0.5 * det.w) * drawW;
        const y = offY + (det.y - 0.5 * det.h) * drawH;
        const w = det.w * drawW;
        const h = det.h * drawH;
        const style = overlayStyle("detection");
        context.setLineDash([]);
        context.strokeStyle = style.stroke;
        context.lineWidth = 2;
        context.strokeRect(x, y, w, h);

        const label = `${det.label} ${det.score.toFixed(2)}`;
        context.font = "12px IBM Plex Mono, monospace";
        const textW = Math.ceil(context.measureText(label).width) + 8;
        context.fillStyle = style.fill;
        context.fillRect(x, Math.max(0, y - 16), textW, 16);
        context.fillStyle = style.text;
        context.fillText(label, x + 4, Math.max(12, y - 4));
      });

      if (targetTrack) {
        lastTargetBoxRef.current = targetTrack;
        const x = offX + (targetTrack.x - 0.5 * targetTrack.w) * drawW;
        const y = offY + (targetTrack.y - 0.5 * targetTrack.h) * drawH;
        const w = targetTrack.w * drawW;
        const h = targetTrack.h * drawH;
        const style = overlayStyle("target");
        context.setLineDash([]);
        context.strokeStyle = style.stroke;
        context.lineWidth = 2.5;
        context.strokeRect(x, y, w, h);

        const label = `TARGET ${targetTrack.id}`;
        context.font = "12px IBM Plex Mono, monospace";
        const textW = Math.ceil(context.measureText(label).width) + 10;
        context.fillStyle = style.fill;
        context.fillRect(x, Math.max(0, y - 18), textW, 18);
        context.fillStyle = style.text;
        context.fillText(label, x + 5, Math.max(13, y - 5));
      } else if (telemetry?.target !== null && telemetry?.target !== undefined && lastTargetBoxRef.current) {
        const lost = lastTargetBoxRef.current;
        const x = offX + (lost.x - 0.5 * lost.w) * drawW;
        const y = offY + (lost.y - 0.5 * lost.h) * drawH;
        const w = lost.w * drawW;
        const h = lost.h * drawH;
        const style = overlayStyle("lost");
        context.strokeStyle = style.stroke;
        context.lineWidth = 2;
        context.setLineDash(style.lineDash ?? [7, 4]);
        context.strokeRect(x, y, w, h);
        context.setLineDash([]);
      }
    };

    resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
    };
  }, [detections, targetTrack, telemetry?.target]);

  const targetStatus = targetTrack ? "LOCKED" : telemetry?.target !== null && telemetry?.target !== undefined ? "LOST" : "IDLE";
  const errorX = targetTrack ? targetTrack.x - 0.5 : null;
  const errorY = targetTrack ? targetTrack.y - 0.5 : null;

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-slate-700/80 bg-slate-900">
      <img ref={videoRef} className="h-full w-full object-contain" src={videoUrl} alt="Dashboard stream" />
      <canvas ref={canvasRef} className="pointer-events-none absolute inset-0 h-full w-full" />

      <div className="pointer-events-none absolute left-2 top-2 flex flex-wrap gap-1.5">
        <StatusBadge tone="info">FPS {fmt(telemetry?.video_fps ?? telemetry?.fps, 1)}</StatusBadge>
        <StatusBadge tone={(telemetry?.latency_ms ?? 0) > 120 ? "warn" : "ok"}>LATENCY {fmt(telemetry?.latency_ms, 1, "ms")}</StatusBadge>
        <StatusBadge tone={targetStatus === "LOCKED" ? "ok" : targetStatus === "LOST" ? "error" : "warn"}>
          TARGET {targetStatus}
        </StatusBadge>
      </div>

      <div className="pointer-events-none absolute right-2 top-2 rounded-md border border-slate-700/80 bg-slate-900/85 px-2 py-1 font-mono text-[11px] text-slate-300">
        ex {fmt(errorX, 3)} | ey {fmt(errorY, 3)}
      </div>

      <div className="pointer-events-none absolute left-1/2 top-1/2 flex h-14 w-14 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-sky-400/45 text-sky-300">
        <Crosshair className="h-7 w-7" />
      </div>

      <div className="pointer-events-none absolute bottom-2 left-2 right-2 grid grid-cols-2 gap-1.5 rounded-md border border-slate-700/80 bg-slate-900/88 p-2 font-mono text-[11px] text-slate-300 md:grid-cols-4">
        <div>
          <span className="text-slate-500">detections</span> {telemetry?.detections.length ?? 0}
        </div>
        <div>
          <span className="text-slate-500">target</span> {telemetry?.target !== null && telemetry?.target !== undefined ? telemetry.target : "--"}
        </div>
        <div>
          <span className="text-slate-500">lock</span>{" "}
          <span className={targetStatus === "LOCKED" ? "text-emerald-300" : targetStatus === "LOST" ? "text-red-300" : "text-amber-300"}>
            {targetStatus}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Radar className="h-3.5 w-3.5 text-sky-300" />
          <span className="text-slate-500">reacquired</span> <span className={reacquired ? "text-emerald-300" : "text-slate-400"}>{reacquired ? "YES" : "NO"}</span>
        </div>
      </div>
    </div>
  );
}
