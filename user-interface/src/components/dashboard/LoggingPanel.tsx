import { useMemo, useState } from "react";
import { Download, Filter, Pause, Play, Trash2 } from "lucide-react";
import { PanelShell } from "@/components/dashboard/PanelShell";
import type { DashboardLogEntry, DashboardLogLevel, DashboardLogSource } from "@/types/dashboard";

const levelChoices: Array<DashboardLogLevel | "all"> = ["all", "debug", "info", "warn", "error"];
const sourceChoices: Array<DashboardLogSource | "all"> = ["all", "socket", "control", "recording", "system"];

interface LoggingPanelProps {
  entries: DashboardLogEntry[];
  isPaused: boolean;
  bufferLimit: number;
  onTogglePaused: () => void;
  onClearLogs: () => void;
  onExportJson: () => void;
  onExportCsv: () => void;
}

export function LoggingPanel({
  entries,
  isPaused,
  bufferLimit,
  onTogglePaused,
  onClearLogs,
  onExportJson,
  onExportCsv,
}: LoggingPanelProps) {
  const [searchText, setSearchText] = useState("");
  const [levelFilter, setLevelFilter] = useState<DashboardLogLevel | "all">("all");
  const [sourceFilter, setSourceFilter] = useState<DashboardLogSource | "all">("all");

  const filteredEntries = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    return entries.filter((entry) => {
      const levelMatch = levelFilter === "all" || entry.level === levelFilter;
      const sourceMatch = sourceFilter === "all" || entry.source === sourceFilter;
      const textMatch =
        query.length === 0 ||
        entry.message.toLowerCase().includes(query) ||
        entry.source.toLowerCase().includes(query) ||
        entry.level.toLowerCase().includes(query);
      return levelMatch && sourceMatch && textMatch;
    });
  }, [entries, levelFilter, searchText, sourceFilter]);

  const levelCounts = useMemo(() => {
    return filteredEntries.reduce<Record<DashboardLogLevel, number>>(
      (acc, entry) => {
        acc[entry.level] += 1;
        return acc;
      },
      { debug: 0, info: 0, warn: 0, error: 0 },
    );
  }, [filteredEntries]);

  const sourceCounts = useMemo(() => {
    return filteredEntries.reduce<Record<DashboardLogSource, number>>(
      (acc, entry) => {
        acc[entry.source] += 1;
        return acc;
      },
      { socket: 0, control: 0, recording: 0, system: 0 },
    );
  }, [filteredEntries]);

  const maxSourceCount = Math.max(...Object.values(sourceCounts), 1);

  const levelClass: Record<DashboardLogLevel, string> = {
    debug: "text-zinc-400 border-zinc-600/70 bg-zinc-800/55",
    info: "text-zinc-200 border-zinc-500/80 bg-zinc-700/40",
    warn: "text-amber-300 border-amber-500/45 bg-amber-500/15",
    error: "text-red-300 border-red-500/45 bg-red-500/15",
  };

  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_auto_minmax(0,1fr)] gap-3">
      <PanelShell
        title="Logging Controls"
        action={<div className="text-[11px] text-zinc-400">{filteredEntries.length} shown / {entries.length} total</div>}
        contentClassName="grid gap-3 p-3"
      >
        <div className="grid gap-3 md:grid-cols-[1.4fr_1fr_1fr]">
          <label className="grid gap-1">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Search Logs</span>
            <input
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Find text, source, or level"
              className="h-9 rounded-md border border-zinc-700 bg-zinc-950/80 px-3 text-sm text-zinc-100 outline-none transition-all placeholder:text-zinc-600 focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500"
            />
          </label>

          <label className="grid gap-1">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Level Filter</span>
            <select
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value as DashboardLogLevel | "all")}
              className="h-9 rounded-md border border-zinc-700 bg-zinc-950/80 px-3 text-sm text-zinc-100 outline-none transition-all focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500"
            >
              {levelChoices.map((level) => (
                <option key={level} value={level}>
                  {level.toUpperCase()}
                </option>
              ))}
            </select>
          </label>

          <label className="grid gap-1">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Source Filter</span>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value as DashboardLogSource | "all")}
              className="h-9 rounded-md border border-zinc-700 bg-zinc-950/80 px-3 text-sm text-zinc-100 outline-none transition-all focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500"
            >
              {sourceChoices.map((source) => (
                <option key={source} value={source}>
                  {source.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onTogglePaused}
            className="inline-flex h-9 items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-900/70 px-3 text-xs font-medium text-zinc-200 transition-all hover:border-zinc-600 hover:bg-zinc-800/80"
          >
            {isPaused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
            {isPaused ? "Resume Intake" : "Pause Intake"}
          </button>

          <button
            type="button"
            onClick={onExportJson}
            className="inline-flex h-9 items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-900/70 px-3 text-xs font-medium text-zinc-200 transition-all hover:border-zinc-600 hover:bg-zinc-800/80"
          >
            <Download className="h-3.5 w-3.5" />
            Export JSON
          </button>

          <button
            type="button"
            onClick={onExportCsv}
            className="inline-flex h-9 items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-900/70 px-3 text-xs font-medium text-zinc-200 transition-all hover:border-zinc-600 hover:bg-zinc-800/80"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </button>

          <button
            type="button"
            onClick={onClearLogs}
            className="inline-flex h-9 items-center gap-1.5 rounded-md border border-red-900/70 bg-red-950/35 px-3 text-xs font-medium text-red-200 transition-all hover:border-red-700 hover:bg-red-900/30"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear Logs
          </button>
        </div>

        <div className="grid gap-2 text-[11px] text-zinc-500 md:grid-cols-3">
          <div className="inline-flex items-center gap-1.5">
            <Filter className="h-3.5 w-3.5" />
            Newest entries first
          </div>
          <div>Intake: {isPaused ? "Paused" : "Live"}</div>
          <div>Buffer limit: {bufferLimit} entries</div>
        </div>
      </PanelShell>

      <div className="grid gap-3 lg:grid-cols-[1fr_1.2fr]">
        <PanelShell title="Level Counters" contentClassName="grid grid-cols-2 gap-2 p-3 sm:grid-cols-4">
          {(["debug", "info", "warn", "error"] as DashboardLogLevel[]).map((level) => (
            <div key={level} className="rounded-md border border-zinc-700/80 bg-zinc-900/60 p-2.5">
              <div className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">{level}</div>
              <div className={`mt-1 text-xl font-semibold ${level === "error" ? "text-red-300" : level === "warn" ? "text-amber-300" : "text-zinc-100"}`}>
                {levelCounts[level]}
              </div>
            </div>
          ))}
        </PanelShell>

        <PanelShell title="Source Distribution" contentClassName="grid gap-2 p-3">
          {(["socket", "control", "recording", "system"] as DashboardLogSource[]).map((source) => {
            const count = sourceCounts[source];
            const pct = Math.round((count / maxSourceCount) * 100);
            return (
              <div key={source} className="grid grid-cols-[88px_minmax(0,1fr)_44px] items-center gap-2">
                <div className="text-[10px] uppercase tracking-[0.14em] text-zinc-400">{source}</div>
                <div className="h-2.5 overflow-hidden rounded-full border border-zinc-700/80 bg-zinc-900/80">
                  <div
                    className={`h-full ${source === "socket" ? "bg-zinc-400" : source === "control" ? "bg-zinc-300" : source === "recording" ? "bg-amber-400" : "bg-red-400"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="text-right font-mono text-[11px] text-zinc-300">{count}</div>
              </div>
            );
          })}
        </PanelShell>
      </div>

      <PanelShell title="Log Stream" className="min-h-0" contentClassName="h-full min-h-0 p-0">
        <div className="h-full min-h-0 overflow-auto">
          {filteredEntries.length === 0 ? (
            <div className="px-3 py-4 text-sm text-zinc-500">No logs match current filters.</div>
          ) : (
            <table className="w-full border-collapse text-left text-xs">
              <thead className="sticky top-0 z-10 bg-zinc-900/95 text-[10px] uppercase tracking-[0.14em] text-zinc-500">
                <tr>
                  <th className="border-b border-zinc-700/70 px-3 py-2">Timestamp</th>
                  <th className="border-b border-zinc-700/70 px-3 py-2">Level</th>
                  <th className="border-b border-zinc-700/70 px-3 py-2">Source</th>
                  <th className="border-b border-zinc-700/70 px-3 py-2">Message</th>
                </tr>
              </thead>
              <tbody>
                {filteredEntries.map((entry) => (
                  <tr key={entry.id} className="border-b border-zinc-800/85 align-top text-zinc-300">
                    <td className="whitespace-nowrap px-3 py-2 font-mono text-[11px] text-zinc-400">{new Date(entry.timestamp_iso).toLocaleString()}</td>
                    <td className="px-3 py-2">
                      <span className={`inline-flex rounded border px-2 py-0.5 font-semibold uppercase ${levelClass[entry.level]}`}>
                        {entry.level}
                      </span>
                    </td>
                    <td className="px-3 py-2 uppercase tracking-[0.08em] text-zinc-400">{entry.source}</td>
                    <td className="px-3 py-2 text-zinc-200">{entry.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </PanelShell>
    </div>
  );
}
