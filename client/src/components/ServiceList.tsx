import { useState } from "react";
import type { ServerConfig, ServiceStatus } from "../lib/agentClient";
import { controlService } from "../lib/agentClient";

function statusClass(active_state: string): string {
  if (active_state === "active") return "active";
  if (active_state === "failed") return "failed";
  return "inactive";
}

export function ServiceList({
  config,
  services,
  onChanged,
}: {
  config: ServerConfig;
  services: ServiceStatus[];
  onChanged: (updated: ServiceStatus) => void;
}) {
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  async function act(name: string, action: "start" | "stop" | "restart") {
    setPending((p) => ({ ...p, [name]: true }));
    setError(null);
    try {
      const updated = await controlService(config, name, action);
      onChanged(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPending((p) => ({ ...p, [name]: false }));
    }
  }

  return (
    <div className="ascii-panel" style={{ flex: 1, overflow: "auto" }}>
      <span className="panel-title">SERVICES</span>
      {error && <div className="meter-bar crit">ERR: {error}</div>}
      <table className="service-table">
        <thead>
          <tr>
            <th>Status</th>
            <th>Service</th>
            <th>State</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {services.map((svc) => (
            <tr key={svc.name}>
              <td>
                <span className={`status-dot ${statusClass(svc.active_state)}`} />
              </td>
              <td>{svc.name}</td>
              <td>
                {svc.active_state}/{svc.sub_state}
              </td>
              <td>
                <button
                  className="retro-btn"
                  disabled={pending[svc.name]}
                  onClick={() => act(svc.name, "start")}
                >
                  start
                </button>
                <button
                  className="retro-btn"
                  disabled={pending[svc.name]}
                  onClick={() => act(svc.name, "stop")}
                >
                  stop
                </button>
                <button
                  className="retro-btn"
                  disabled={pending[svc.name]}
                  onClick={() => act(svc.name, "restart")}
                >
                  restart
                </button>
              </td>
            </tr>
          ))}
          {services.length === 0 && (
            <tr>
              <td colSpan={4}>no allowed services configured on agent</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
