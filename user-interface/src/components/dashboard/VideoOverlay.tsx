import { useEffect, useMemo, useRef } from "react";
import type { DashboardTelemetry } from "@/types/dashboard";

interface VideoOverlayProps {
  telemetry: DashboardTelemetry | null;
  videoUrl: string;
}

export function VideoOverlay({ telemetry, videoUrl }: VideoOverlayProps) {
  const videoRef = useRef<HTMLImageElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const detections = useMemo(() => telemetry?.detections ?? [], [telemetry]);

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

      detections.forEach((det) => {
        const x = offX + (det.x - 0.5 * det.w) * drawW;
        const y = offY + (det.y - 0.5 * det.h) * drawH;
        const w = det.w * drawW;
        const h = det.h * drawH;
        context.strokeStyle = "#14b8a6";
        context.lineWidth = 2;
        context.strokeRect(x, y, w, h);

        const label = `${det.label} ${det.score.toFixed(2)}`;
        context.font = "12px IBM Plex Mono, monospace";
        const textW = Math.ceil(context.measureText(label).width) + 8;
        context.fillStyle = "#14b8a6";
        context.fillRect(x, Math.max(0, y - 16), textW, 16);
        context.fillStyle = "#ffffff";
        context.fillText(label, x + 4, Math.max(12, y - 4));
      });
    };

    resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
    };
  }, [detections]);

  return (
    <div className="relative aspect-square w-full overflow-hidden rounded-md bg-slate-900">
      <img ref={videoRef} className="h-full w-full object-contain" src={videoUrl} alt="Dashboard stream" />
      <canvas ref={canvasRef} className="pointer-events-none absolute inset-0 h-full w-full" />
    </div>
  );
}
