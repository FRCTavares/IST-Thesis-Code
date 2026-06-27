import { useEffect, useRef, useState } from "react";
import { BarChart3, ChevronRight, LayoutDashboard, LogOut, Radar, ScrollText, Settings, SlidersHorizontal } from "lucide-react";
import { DashboardWebSocketProvider, useDashboardRealtime } from "@/features/dashboard/providers/dashboardWebSocketProvider";
import { VideoOverlay } from "@/components/dashboard/VideoOverlay";
import { SystemMetricsGrid } from "@/components/dashboard/SystemMetricsGrid";
import { ChartsWorkspace } from "@/components/dashboard/ChartsWorkspace";
import { PerceptionTrackingPanel } from "@/components/dashboard/PerceptionTrackingPanel";
import { StatusPanel } from "@/components/dashboard/StatusPanel";
import { ControlPanel } from "@/components/dashboard/ControlPanel";
import { LoggingPanel } from "@/components/dashboard/LoggingPanel";
import { PanelShell } from "@/components/dashboard/PanelShell";
import { dashboardConfig } from "@/services/config";
import type {
  DashboardLogEntry,
  DashboardLogLevel,
  DashboardLogSource,
  DashboardModel,
  DashboardSupportedModel,
  DashboardTracker,
  MetricsSnapshot,
} from "@/types/dashboard";
import { useDashboardMetrics } from "@/features/dashboard/hooks/useDashboardMetrics";
import { fetchSupportedModels, requestModelSwitch, requestTargetFocus, requestTrackerSwitch } from "@/features/dashboard/services/dashboardApi";
import { exportMetricsCsv } from "@/features/dashboard/utils/csv";

type DashboardTab = "overview" | "control" | "charts" | "logging";
type UiDensity = "compact" | "cozy";

const DEFAULT_LOG_BUFFER_LIMIT = 2000;
const DASHBOARD_LOGS_STORAGE_KEY = "dashboard.log.entries.v1";
const DASHBOARD_LOGS_PAUSED_STORAGE_KEY = "dashboard.log.paused.v1";
const DASHBOARD_UI_DENSITY_STORAGE_KEY = "dashboard.ui.density.v1";
const DASHBOARD_DEFAULT_TAB_STORAGE_KEY = "dashboard.ui.defaultTab.v1";
const DASHBOARD_LOG_BUFFER_STORAGE_KEY = "dashboard.log.bufferLimit.v1";
const FALLBACK_MODELS: DashboardModel[] = ["yolov6n", "yolov8s", "yolov8m"];

interface SavedRecording {
  id: string;
  createdAtIso: string;
  model: DashboardModel;
  tracker: DashboardTracker;
  samples: MetricsSnapshot[];
}

interface StreamResolution {
  width: number;
  height: number;
}

function inferLogLevel(message: string): DashboardLogLevel {
  const text = message.toLowerCase();
  if (/(error|failed|fail|cannot|down|invalid)/.test(text)) {
    return "error";
  }
  if (/(warn|degrad|retry|slow|closing)/.test(text)) {
    return "warn";
  }
  if (/(started|stopped|requested|connected|live|downloaded|deleted|cleared)/.test(text)) {
    return "info";
  }
  return "debug";
}

function isDashboardTab(value: string): value is DashboardTab {
  return value === "overview" || value === "control" || value === "charts" || value === "logging";
}

function DashboardPage() {
  const { telemetry, status } = useDashboardRealtime();
  const [activeModel, setActiveModel] = useState<DashboardModel>("yolov6n");
  const [availableModels, setAvailableModels] = useState<DashboardModel[]>(FALLBACK_MODELS);
  const [activeTracker, setActiveTracker] = useState<DashboardTracker>("sort");
  const [controlStatus, setControlStatus] = useState("Recording idle. Start recording to collect CSV samples.");
  const [samples, setSamples] = useState<MetricsSnapshot[]>([]);
  const [recordedSamples, setRecordedSamples] = useState<MetricsSnapshot[]>([]);
  const [savedRecordings, setSavedRecordings] = useState<SavedRecording[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isModelSwitching, setIsModelSwitching] = useState(false);
  const [isTrackerSwitching, setIsTrackerSwitching] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [logEntries, setLogEntries] = useState<DashboardLogEntry[]>([]);
  const [isLogIntakePaused, setIsLogIntakePaused] = useState(false);
  const [uiDensity, setUiDensity] = useState<UiDensity>("cozy");
  const [defaultTab, setDefaultTab] = useState<DashboardTab>("overview");
  const [logBufferLimit, setLogBufferLimit] = useState(DEFAULT_LOG_BUFFER_LIMIT);
  const [streamResolution, setStreamResolution] = useState<StreamResolution | null>(null);

  const lastSocketStatusRef = useRef<string | null>(null);
  const lastControlStatusRef = useRef<string | null>(null);

  const hasTelemetry = Boolean(telemetry);
  const statusLower = status.toLowerCase();
  const explicitlyDisconnected = /(disconnected|retry|error|fail|closed|closing|connecting)/.test(statusLower);
  const explicitlyConnected = /(connected|live|open)/.test(statusLower);
  const isLinkUp = hasTelemetry || (explicitlyConnected && !explicitlyDisconnected);
  const streamResolutionLabel = streamResolution ? `${streamResolution.width}x${streamResolution.height}` : "Unknown";
  const inferenceResolutionLabel = telemetry?.inference_resolution
    ? `${telemetry.inference_resolution.width}x${telemetry.inference_resolution.height}`
    : streamResolutionLabel;

  const metricState = useDashboardMetrics(telemetry, activeModel);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const response = await fetchSupportedModels();
      if (cancelled || !response.ok || !response.models) {
        return;
      }

      const available = response.models
        .filter((model: DashboardSupportedModel) => model.available)
        .map((model: DashboardSupportedModel) => model.key);
      if (available.length === 0) {
        return;
      }

      setAvailableModels(available);
      setActiveModel((current) => (available.includes(current) ? current : available[0]));
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    try {
      let loadedBufferLimit = DEFAULT_LOG_BUFFER_LIMIT;
      const rawBufferLimit = window.localStorage.getItem(DASHBOARD_LOG_BUFFER_STORAGE_KEY);
      if (rawBufferLimit) {
        const parsedLimit = Number(rawBufferLimit);
        if ([500, 1000, 2000, 5000].includes(parsedLimit)) {
          loadedBufferLimit = parsedLimit;
          setLogBufferLimit(parsedLimit);
        }
      }

      const rawDensity = window.localStorage.getItem(DASHBOARD_UI_DENSITY_STORAGE_KEY);
      if (rawDensity === "compact" || rawDensity === "cozy") {
        setUiDensity(rawDensity);
      }

      const rawDefaultTab = window.localStorage.getItem(DASHBOARD_DEFAULT_TAB_STORAGE_KEY);
      if (rawDefaultTab && isDashboardTab(rawDefaultTab)) {
        setDefaultTab(rawDefaultTab);
        setActiveTab(rawDefaultTab);
      }

      const rawLogs = window.localStorage.getItem(DASHBOARD_LOGS_STORAGE_KEY);
      if (rawLogs) {
        const parsed = JSON.parse(rawLogs) as DashboardLogEntry[];
        if (Array.isArray(parsed)) {
          const sanitized = parsed
            .filter((entry) => entry && typeof entry.message === "string" && typeof entry.timestamp_iso === "string")
            .slice(0, loadedBufferLimit);
          if (sanitized.length > 0) {
            setLogEntries(sanitized);
          }
        }
      }

      const rawPaused = window.localStorage.getItem(DASHBOARD_LOGS_PAUSED_STORAGE_KEY);
      if (rawPaused === "1") {
        setIsLogIntakePaused(true);
      }
    } catch {
      // Ignore storage parse errors and continue with defaults.
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(DASHBOARD_LOGS_STORAGE_KEY, JSON.stringify(logEntries));
    } catch {
      // Ignore storage write errors when localStorage is unavailable.
    }
  }, [logEntries]);

  useEffect(() => {
    try {
      window.localStorage.setItem(DASHBOARD_LOGS_PAUSED_STORAGE_KEY, isLogIntakePaused ? "1" : "0");
    } catch {
      // Ignore storage write errors when localStorage is unavailable.
    }
  }, [isLogIntakePaused]);

  useEffect(() => {
    try {
      window.localStorage.setItem(DASHBOARD_UI_DENSITY_STORAGE_KEY, uiDensity);
      window.localStorage.setItem(DASHBOARD_DEFAULT_TAB_STORAGE_KEY, defaultTab);
      window.localStorage.setItem(DASHBOARD_LOG_BUFFER_STORAGE_KEY, String(logBufferLimit));
    } catch {
      // Ignore storage write errors when localStorage is unavailable.
    }
  }, [defaultTab, logBufferLimit, uiDensity]);

  useEffect(() => {
    setLogEntries((prev) => prev.slice(0, logBufferLimit));
  }, [logBufferLimit]);

  const appendLog = (source: DashboardLogSource, message: string, level?: DashboardLogLevel) => {
    if (isLogIntakePaused) {
      return;
    }
    const entry: DashboardLogEntry = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      timestamp_iso: new Date().toISOString(),
      source,
      level: level ?? inferLogLevel(message),
      message,
    };
    setLogEntries((prev) => [entry, ...prev].slice(0, logBufferLimit));
  };

  useEffect(() => {
    const snapshot = metricState.snapshot;
    if (!snapshot) {
      return;
    }
    setSamples((prev: MetricsSnapshot[]) => {
      const next = [...prev, snapshot];
      if (next.length > 2400) {
        next.shift();
      }
      return next;
    });

    if (!isRecording) {
      return;
    }

    setRecordedSamples((prev: MetricsSnapshot[]) => {
      const next = [...prev, snapshot];
      if (next.length > 7200) {
        next.shift();
      }
      return next;
    });
  }, [isRecording, metricState.snapshot]);

  useEffect(() => {
    if (!status) {
      return;
    }
    if (lastSocketStatusRef.current === status) {
      return;
    }
    appendLog("socket", status);
    lastSocketStatusRef.current = status;
  }, [status]);

  useEffect(() => {
    if (!controlStatus) {
      return;
    }
    if (lastControlStatusRef.current === controlStatus) {
      return;
    }
    appendLog("control", controlStatus);
    lastControlStatusRef.current = controlStatus;
  }, [controlStatus]);

  const handleModelSwitch = async (model: DashboardModel) => {
    if (!isLinkUp) {
      setControlStatus("Cannot switch model while link is down.");
      return;
    }
    setIsModelSwitching(true);
    const response = await requestModelSwitch(model);
    if (response.ok) {
      setActiveModel(model);
      setControlStatus(`Model switch requested: ${model}`);
      setIsModelSwitching(false);
      return;
    }
    setControlStatus(
      `Model switch failed (${dashboardConfig.apiBaseUrl}/api/model): ${response.error ?? "unknown error"}`,
    );
    setIsModelSwitching(false);
  };

  const handleTrackerSwitch = async (tracker: DashboardTracker) => {
    if (!isLinkUp) {
      setControlStatus("Cannot switch tracker while link is down.");
      return;
    }
    setIsTrackerSwitching(true);
    const response = await requestTrackerSwitch(tracker);
    if (response.ok) {
      setActiveTracker(tracker);
      setControlStatus(`Tracker switch requested: ${tracker}`);
      setIsTrackerSwitching(false);
      return;
    }
    setControlStatus(
      `Tracker switch failed (${dashboardConfig.apiBaseUrl}/api/tracker): ${response.error ?? "unknown error"}`,
    );
    setIsTrackerSwitching(false);
  };

  const handleStartRecording = () => {
    if (!isLinkUp) {
      setControlStatus("Cannot start recording while link is down.");
      return;
    }
    setRecordedSamples([]);
    setIsRecording(true);
    setControlStatus("Recording started. Capturing live telemetry samples.");
    appendLog("recording", "Recording started. Capturing live telemetry samples.", "info");
  };

  const handleStopRecording = () => {
    setIsRecording(false);
    if (recordedSamples.length > 0) {
      const saved: SavedRecording = {
        id: `${Date.now()}`,
        createdAtIso: new Date().toISOString(),
        model: activeModel,
        tracker: activeTracker,
        samples: [...recordedSamples],
      };
      setSavedRecordings((prev) => [saved, ...prev]);
    }
    setControlStatus(`Recording stopped. Captured ${recordedSamples.length} samples.`);
    appendLog("recording", `Recording stopped. Captured ${recordedSamples.length} samples.`, "info");
  };

  const handleDownloadRecording = (id: string) => {
    const selected = savedRecordings.find((entry) => entry.id === id);
    if (!selected) {
      return;
    }
    exportMetricsCsv(selected.samples, selected.model);
    setControlStatus(`Downloaded recording (${selected.samples.length} samples).`);
    appendLog("recording", `Downloaded recording (${selected.samples.length} samples).`, "info");
  };

  const handleDeleteRecording = (id: string) => {
    const selected = savedRecordings.find((entry) => entry.id === id);
    setSavedRecordings((prev) => prev.filter((entry) => entry.id !== id));
    if (selected) {
      setControlStatus(`Deleted recording (${selected.samples.length} samples).`);
      appendLog("recording", `Deleted recording (${selected.samples.length} samples).`, "warn");
    }
  };

  const handleTargetFocus = async (target: number | null) => {
    if (!isLinkUp) {
      setControlStatus("Cannot change target focus while link is down.");
      return;
    }
    const response = await requestTargetFocus(target);
    if (response.ok) {
      setControlStatus(target === null ? "Target focus set to AUTO." : `Target focus requested: #${target}`);
      return;
    }
    setControlStatus(`Target focus failed (${dashboardConfig.apiBaseUrl}/api/target): ${response.error ?? "unknown error"}`);
  };

  const handleLogout = () => {
    appendLog("system", "Logout requested. Session state cleared.", "warn");
    setIsRecording(false);
    setSamples([]);
    setRecordedSamples([]);
    setSavedRecordings([]);
    setStreamResolution(null);
    setActiveTab(defaultTab);
    setIsSidebarCollapsed(false);
    setIsSettingsOpen(false);
    setControlStatus("Logged out. Session state cleared.");
  };

  const handleExportLogsJson = () => {
    const blob = new Blob([JSON.stringify(logEntries, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `dashboard_logs_${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    setControlStatus(`Exported ${logEntries.length} log entries to JSON.`);
  };

  const handleExportLogsCsv = () => {
    const escape = (value: string) => `"${value.replace(/"/g, '""')}"`;
    const rows = [
      ["timestamp_iso", "level", "source", "message"],
      ...logEntries.map((entry) => [entry.timestamp_iso, entry.level, entry.source, entry.message]),
    ];
    const csv = rows.map((row) => row.map((cell) => escape(String(cell))).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `dashboard_logs_${new Date().toISOString().replace(/[:.]/g, "-")}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
    setControlStatus(`Exported ${logEntries.length} log entries to CSV.`);
  };

  const handleClearLogs = () => {
    setLogEntries([]);
    setControlStatus("Logs cleared.");
  };

  return (
    <div className={`min-h-screen w-full ui-density-${uiDensity}`}>
      <aside className="fixed inset-y-0 left-0 z-40 flex w-[92px] flex-col items-center justify-between border-r border-zinc-700/80 bg-zinc-800/70 py-4">
        <div className="flex flex-col items-center gap-2">
          <div className="flex flex-col items-center gap-1 select-none" aria-hidden="true">
            <Radar className="h-6 w-6 text-zinc-300/90" />
            <div className="text-[9px] font-semibold uppercase tracking-[0.22em] text-zinc-500">UAV</div>
          </div>

          <div className="mb-2 mt-2 h-px w-10 bg-zinc-700/80" />

          <button
            type="button"
            onClick={() => setActiveTab("overview")}
            className={`flex h-12 w-12 items-center justify-center rounded-lg border transition-all ${activeTab === "overview"
              ? "border-zinc-500/70 bg-zinc-700/40 text-zinc-100 shadow-[0_0_14px_rgba(100,116,139,0.18)]"
              : "border-zinc-800 bg-zinc-900/65 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
              }`}
            aria-label="Overview"
            title="Overview"
          >
            <LayoutDashboard className="h-6 w-6" />
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("control")}
            className={`flex h-12 w-12 items-center justify-center rounded-lg border transition-all ${activeTab === "control"
              ? "border-zinc-500/70 bg-zinc-700/40 text-zinc-100 shadow-[0_0_14px_rgba(100,116,139,0.18)]"
              : "border-zinc-800 bg-zinc-900/65 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
              }`}
            aria-label="Control"
            title="Control"
          >
            <SlidersHorizontal className="h-6 w-6" />
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("charts")}
            className={`flex h-12 w-12 items-center justify-center rounded-lg border transition-all ${activeTab === "charts"
              ? "border-zinc-500/70 bg-zinc-700/40 text-zinc-100 shadow-[0_0_14px_rgba(100,116,139,0.18)]"
              : "border-zinc-800 bg-zinc-900/65 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
              }`}
            aria-label="Charts"
            title="Charts"
          >
            <BarChart3 className="h-6 w-6" />
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("logging")}
            className={`flex h-12 w-12 items-center justify-center rounded-lg border transition-all ${activeTab === "logging"
              ? "border-zinc-500/70 bg-zinc-700/40 text-zinc-100 shadow-[0_0_14px_rgba(100,116,139,0.18)]"
              : "border-zinc-800 bg-zinc-900/65 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
              }`}
            aria-label="Logging"
            title="Logging"
          >
            <ScrollText className="h-6 w-6" />
          </button>
        </div>

        <div className="flex flex-col items-center gap-2">
          <div className="mb-1 h-px w-10 bg-zinc-700/80" />
          <button
            type="button"
            onClick={() => setIsSettingsOpen(true)}
            className="flex h-12 w-12 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900/65 text-zinc-400 transition-all hover:border-zinc-600 hover:text-zinc-200"
            aria-label="Settings"
            title="Settings"
          >
            <Settings className="h-6 w-6" />
          </button>

          <button
            type="button"
            onClick={handleLogout}
            className="flex h-12 w-12 items-center justify-center rounded-lg border border-red-900/80 bg-red-950/45 text-red-300 transition-all hover:border-red-700 hover:bg-red-900/35 hover:text-red-200"
            aria-label="Disconnect"
            title="Disconnect / Logout"
          >
            <LogOut className="h-6 w-6" />
          </button>
        </div>
      </aside>

      <main className="min-h-screen pl-[92px]">
        <div className={`mx-auto w-full max-w-[1640px] ${uiDensity === "compact" ? "p-2 lg:p-3" : "p-3 lg:p-4"}`}>
          {isSidebarCollapsed && (
            <div className="mb-3 flex justify-end">
              <button
                type="button"
                onClick={() => setIsSidebarCollapsed(false)}
                className="h-9 w-9 rounded-md border border-zinc-700/80 bg-zinc-900/90 text-zinc-300 shadow-[0_8px_24px_rgba(2,6,23,0.35)] transition-all hover:border-zinc-500 hover:text-zinc-100"
                aria-label="Expand side panel"
                title="Expand side panel"
              >
                <ChevronRight className="mx-auto h-4 w-4" />
              </button>
            </div>
          )}

          {activeTab === "overview" ? (
            <div className={`grid grid-cols-1 gap-3 transition-[grid-template-columns] duration-300 ease-in-out ${isSidebarCollapsed ? "lg:grid-cols-1" : "lg:grid-cols-[2.2fr_1fr]"} lg:min-h-[calc(100vh-2rem)] lg:items-stretch`}>
              <section className="grid h-full grid-rows-[minmax(0,1fr)_auto_auto] gap-3">
                <PanelShell title="Live Camera Feed" className="flex h-full flex-col" contentClassName="min-h-0 flex-1 p-2.5">
                  <VideoOverlay telemetry={telemetry} videoUrl={dashboardConfig.videoUrl} onResolutionChange={setStreamResolution} />
                </PanelShell>
                <PerceptionTrackingPanel snapshot={metricState.snapshot} telemetry={telemetry} />
                <SystemMetricsGrid snapshot={metricState.snapshot} />
              </section>

              {!isSidebarCollapsed && (
                <StatusPanel status={status} mode={dashboardConfig.mode} telemetry={telemetry} snapshot={metricState.snapshot} activeModel={activeModel} availableModels={availableModels} activeTracker={activeTracker} onModelSwitch={handleModelSwitch} onTrackerSwitch={handleTrackerSwitch} onStartRecording={handleStartRecording} onStopRecording={handleStopRecording} isRecording={isRecording} recordedCount={recordedSamples.length} onCloseSidebar={() => setIsSidebarCollapsed(true)} isModelSwitching={isModelSwitching} isTrackerSwitching={isTrackerSwitching} controlStatus={controlStatus} recordings={savedRecordings.map((entry) => ({ id: entry.id, createdAtIso: entry.createdAtIso, model: entry.model, tracker: entry.tracker, sampleCount: entry.samples.length }))} onDownloadRecording={handleDownloadRecording} onDeleteRecording={handleDeleteRecording} isLinkUp={isLinkUp} currentResolutionLabel={inferenceResolutionLabel} />
              )}
            </div>
          ) : null}

          {activeTab === "control" ? (
            <div className="grid grid-cols-1 gap-3 lg:min-h-[calc(100vh-2rem)] lg:items-stretch">
              <ControlPanel
                activeModel={activeModel}
                availableModels={availableModels}
                activeTracker={activeTracker}
                onModelSwitch={handleModelSwitch}
                onTrackerSwitch={handleTrackerSwitch}
                onTargetFocus={handleTargetFocus}
                availableTrackIds={telemetry?.tracks.map((track) => track.id) ?? []}
                currentTargetId={telemetry?.target ?? null}
                isModelSwitching={isModelSwitching}
                isTrackerSwitching={isTrackerSwitching}
                controlStatus={controlStatus}
                isLinkUp={isLinkUp}
                currentResolutionLabel={inferenceResolutionLabel}
              />
            </div>
          ) : null}

          {activeTab === "charts" ? (
            <div className="grid grid-cols-1 gap-3">
              <ChartsWorkspace samples={samples} />
            </div>
          ) : null}

          {activeTab === "logging" ? (
            <div className="grid grid-cols-1 gap-3 lg:min-h-[calc(100vh-2rem)] lg:items-stretch">
              <LoggingPanel
                entries={logEntries}
                isPaused={isLogIntakePaused}
                bufferLimit={logBufferLimit}
                onTogglePaused={() => setIsLogIntakePaused((prev) => !prev)}
                onClearLogs={handleClearLogs}
                onExportJson={handleExportLogsJson}
                onExportCsv={handleExportLogsCsv}
              />
            </div>
          ) : null}
        </div>
      </main>

      {isSettingsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
          <div className="w-full max-w-md rounded-lg border border-zinc-700/80 bg-zinc-900/95 p-4 shadow-[0_20px_50px_rgba(0,0,0,0.45)]">
            <div className="mb-3 text-[12px] font-semibold uppercase tracking-[0.14em] text-zinc-400">Settings</div>
            <div className="space-y-3 rounded-md border border-zinc-700/70 bg-zinc-900/60 p-3 text-sm text-zinc-300">
              <div className="space-y-1">
                <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Density</div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setUiDensity("compact")}
                    className={`h-8 rounded-md border px-3 text-xs transition-all ${uiDensity === "compact"
                      ? "border-zinc-500 bg-zinc-700/50 text-zinc-100"
                      : "border-zinc-700 bg-zinc-900/70 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
                      }`}
                  >
                    Compact
                  </button>
                  <button
                    type="button"
                    onClick={() => setUiDensity("cozy")}
                    className={`h-8 rounded-md border px-3 text-xs transition-all ${uiDensity === "cozy"
                      ? "border-zinc-500 bg-zinc-700/50 text-zinc-100"
                      : "border-zinc-700 bg-zinc-900/70 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
                      }`}
                  >
                    Cozy
                  </button>
                </div>
              </div>

              <label className="grid gap-1">
                <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Default Tab</span>
                <select
                  value={defaultTab}
                  onChange={(e) => setDefaultTab(e.target.value as DashboardTab)}
                  className="h-9 rounded-md border border-zinc-700 bg-zinc-950/80 px-3 text-sm text-zinc-100 transition-all focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500"
                >
                  <option value="overview">Overview</option>
                  <option value="control">Control</option>
                  <option value="charts">Charts</option>
                  <option value="logging">Logging</option>
                </select>
              </label>

              <label className="grid gap-1">
                <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Log Buffer Limit</span>
                <select
                  value={logBufferLimit}
                  onChange={(e) => setLogBufferLimit(Number(e.target.value))}
                  className="h-9 rounded-md border border-zinc-700 bg-zinc-950/80 px-3 text-sm text-zinc-100 transition-all focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500"
                >
                  <option value={500}>500 entries</option>
                  <option value={1000}>1000 entries</option>
                  <option value={2000}>2000 entries</option>
                  <option value={5000}>5000 entries</option>
                </select>
              </label>
            </div>
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={() => setIsSettingsOpen(false)}
                className="inline-flex h-9 items-center justify-center rounded-md border border-zinc-700 bg-zinc-900 px-3 text-sm text-zinc-200 transition-all hover:border-zinc-500 hover:text-zinc-100"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function App() {
  return (
    <DashboardWebSocketProvider>
      <DashboardPage />
    </DashboardWebSocketProvider>
  );
}
