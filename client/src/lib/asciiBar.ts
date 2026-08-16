export function asciiBar(percent: number, width = 24): string {
  const clamped = Math.max(0, Math.min(100, percent));
  const filled = Math.round((clamped / 100) * width);
  return `[${"#".repeat(filled)}${"-".repeat(width - filled)}]`;
}

export function severity(percent: number): "ok" | "warn" | "crit" {
  if (percent >= 90) return "crit";
  if (percent >= 70) return "warn";
  return "ok";
}

export function formatBytes(bytes: number): string {
  const gb = bytes / 1024 ** 3;
  if (gb >= 1) return `${gb.toFixed(1)}G`;
  const mb = bytes / 1024 ** 2;
  return `${mb.toFixed(0)}M`;
}

export function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${d}d ${h}h ${m}m`;
}
