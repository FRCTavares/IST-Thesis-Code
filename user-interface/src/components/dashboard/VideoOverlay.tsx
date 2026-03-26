import { useEffect, useMemo, useRef, useState } from "react";
import { Crosshair, Loader2 } from "lucide-react";
import type { DashboardTelemetry } from "@/types/dashboard";
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
  const [videoLoaded, setVideoLoaded] = useState(false);

  const detections = useMemo(() => telemetry?.detections ?? [], [telemetry]);
  const targetTrack = useMemo(() => {
    if (!telemetry || telemetry.target === null || telemetry.target === undefined) {
      return null;
    }
    return telemetry.tracks.find((track) => track.id === telemetry.target) ?? null;
  }, [telemetry]);

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

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-slate-700/80 bg-slate-900">
      <img
        ref={videoRef}
        className="h-full w-full object-contain"
        style={{ visibility: videoLoaded ? 'visible' : 'hidden' }}
        src={videoUrl}
        alt="Dashboard stream"
        onLoad={() => setVideoLoaded(true)}
        onError={() => setVideoLoaded(false)}
      />
      <canvas ref={canvasRef} className="pointer-events-none absolute inset-0 h-full w-full" />

      {!videoLoaded && telemetry === null && (
        <div className="pointer-events-none absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-2">
          <Loader2 className="h-12 w-12 animate-spin text-sky-400" />
          <div className="text-xs text-slate-400">Connecting...</div>
        </div>
      )}

      {videoLoaded && (
        <div className="pointer-events-none absolute left-1/2 top-1/2 flex h-14 w-14 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-sky-400/45 text-sky-300">
          <Crosshair className="h-7 w-7" />
        </div>
      )}

    </div>
  );
}
