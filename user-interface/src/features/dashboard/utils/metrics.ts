export function pushSeries(arr: number[], value: number | null | undefined, maxLen = 240): void {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return;
  }
  arr.push(Number(value));
  if (arr.length > maxLen) {
    arr.shift();
  }
}

export function mean(arr: number[]): number | null {
  if (!arr.length) {
    return null;
  }
  return arr.reduce((sum, value) => sum + value, 0) / arr.length;
}

export function percentile(arr: number[], p: number): number | null {
  if (!arr.length) {
    return null;
  }
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.floor((p / 100) * (sorted.length - 1))));
  return sorted[idx] ?? null;
}

export function fmt(value: number | null | undefined, digits = 1, unit = ""): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }
  return `${Number(value).toFixed(digits)}${unit}`;
}
