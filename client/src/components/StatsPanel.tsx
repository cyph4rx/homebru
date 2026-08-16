import type { AllStats } from "../lib/agentClient";
import { asciiBar, formatBytes, formatUptime, severity } from "../lib/asciiBar";

function Meter({ label, percent, extra }: { label: string; percent: number; extra?: string }) {
  return (
    <div className="meter-row">
      <span className="meter-label">{label}</span>
      <span className={`meter-bar ${severity(percent)}`}>{asciiBar(percent)}</span>
      <span className="meter-value">
        {percent.toFixed(0)}%{extra ? ` ${extra}` : ""}
      </span>
    </div>
  );
}

export function StatsPanel({ stats }: { stats: AllStats | null }) {
  if (!stats) {
    return (
      <div className="ascii-panel">
        <span className="panel-title">SYSTEM STATS</span>
        <div>
          awaiting data<span className="blink">_</span>
        </div>
      </div>
    );
  }

  const mem = stats.memory;
  const memExtra = `${formatBytes(mem.used)}/${formatBytes(mem.total)}`;

  return (
    <div className="ascii-panel">
      <span className="panel-title">SYSTEM STATS</span>
      <div className="panel-row">
        <span>UPTIME: {formatUptime(stats.uptime_seconds)}</span>
      </div>

      <Meter label="CPU" percent={stats.cpu.percent} extra={`${stats.cpu.core_count} cores`} />
      <Meter label="MEM" percent={mem.percent} extra={memExtra} />

      {stats.gpus.length === 0 && (
        <div className="meter-row">
          <span className="meter-label">GPU</span>
          <span>n/a</span>
        </div>
      )}
      {stats.gpus.map((gpu, i) => (
        <Meter
          key={i}
          label={stats.gpus.length > 1 ? `GPU${i}` : "GPU"}
          percent={gpu.utilization_percent}
          extra={`${gpu.temperature_c.toFixed(0)}C ${formatBytes(gpu.memory_used_mb * 1024 ** 2)}/${formatBytes(
            gpu.memory_total_mb * 1024 ** 2,
          )}`}
        />
      ))}

      {stats.disks.map((disk) => (
        <Meter
          key={disk.mountpoint}
          label={disk.mountpoint.length > 10 ? disk.mountpoint.slice(0, 9) + "…" : disk.mountpoint}
          percent={disk.percent}
          extra={`${formatBytes(disk.used)}/${formatBytes(disk.total)}`}
        />
      ))}
    </div>
  );
}
