import { useState } from "react";
import type { ServerConfig } from "../lib/agentClient";

export function ConnectSetup({ onConnect }: { onConnect: (config: ServerConfig) => void }) {
  const [host, setHost] = useState("");
  const [port, setPort] = useState("8420");
  const [token, setToken] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!host.trim() || !token.trim()) return;
    onConnect({ host: host.trim(), port: Number(port) || 8420, token: token.trim() });
  }

  return (
    <div className="terminal-window">
      <div className="ascii-panel" style={{ maxWidth: 480, margin: "auto" }}>
        <span className="panel-title">CONNECT TO SERVER</span>
        <form onSubmit={submit}>
          <div className="meter-row">
            <span className="meter-label">HOST</span>
            <input
              className="retro-input"
              style={{ flex: 1 }}
              value={host}
              onChange={(e) => setHost(e.target.value)}
              placeholder="192.168.1.50"
              autoFocus
            />
          </div>
          <div className="meter-row">
            <span className="meter-label">PORT</span>
            <input
              className="retro-input"
              style={{ flex: 1 }}
              value={port}
              onChange={(e) => setPort(e.target.value)}
            />
          </div>
          <div className="meter-row">
            <span className="meter-label">TOKEN</span>
            <input
              className="retro-input"
              style={{ flex: 1 }}
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
          </div>
          <button className="retro-btn" type="submit" style={{ marginTop: 10 }}>
            [ CONNECT ]
          </button>
        </form>
      </div>
    </div>
  );
}
