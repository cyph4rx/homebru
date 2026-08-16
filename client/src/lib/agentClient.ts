export interface ServerConfig {
  host: string;
  port: number;
  token: string;
}

export interface CpuStats {
  percent: number;
  per_core: number[];
  core_count: number;
}

export interface MemoryStats {
  total: number;
  used: number;
  percent: number;
}

export interface DiskStats {
  mountpoint: string;
  total: number;
  used: number;
  percent: number;
}

export interface GpuStats {
  name: string;
  utilization_percent: number;
  memory_used_mb: number;
  memory_total_mb: number;
  temperature_c: number;
}

export interface AllStats {
  uptime_seconds: number;
  cpu: CpuStats;
  memory: MemoryStats;
  disks: DiskStats[];
  gpus: GpuStats[];
  timestamp: number;
}

export interface ServiceStatus {
  name: string;
  active_state: string;
  sub_state: string;
  enabled: string;
  description: string;
}

function baseUrl(config: ServerConfig): string {
  return `http://${config.host}:${config.port}`;
}

function wsUrl(config: ServerConfig): string {
  return `ws://${config.host}:${config.port}/ws/stats?token=${encodeURIComponent(config.token)}`;
}

export async function fetchServices(config: ServerConfig): Promise<ServiceStatus[]> {
  const res = await fetch(`${baseUrl(config)}/services`, {
    headers: { Authorization: `Bearer ${config.token}` },
  });
  if (!res.ok) throw new Error(`failed to fetch services: ${res.status}`);
  return res.json();
}

export async function controlService(
  config: ServerConfig,
  name: string,
  action: "start" | "stop" | "restart",
): Promise<ServiceStatus> {
  const res = await fetch(`${baseUrl(config)}/services/${encodeURIComponent(name)}/${action}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${config.token}` },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `failed to ${action} ${name}`);
  }
  return res.json();
}

type StatsListener = (stats: AllStats) => void;
type ConnectionListener = (connected: boolean) => void;

export class StatsSocket {
  private ws: WebSocket | null = null;
  private reconnectTimer: number | null = null;
  private closed = false;
  private config: ServerConfig;
  private onStats: StatsListener;
  private onConnectionChange: ConnectionListener;

  constructor(config: ServerConfig, onStats: StatsListener, onConnectionChange: ConnectionListener) {
    this.config = config;
    this.onStats = onStats;
    this.onConnectionChange = onConnectionChange;
  }

  connect(): void {
    this.closed = false;
    this.ws = new WebSocket(wsUrl(this.config));

    this.ws.onopen = () => this.onConnectionChange(true);

    this.ws.onmessage = (event) => {
      try {
        this.onStats(JSON.parse(event.data));
      } catch {
        // ignore malformed frame
      }
    };

    this.ws.onclose = () => {
      this.onConnectionChange(false);
      if (!this.closed) this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.closed) this.connect();
    }, 3000);
  }

  close(): void {
    this.closed = true;
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
  }
}
