import { useEffect, useRef, useState } from "react";
import { ConnectSetup } from "./components/ConnectSetup";
import { ServiceList } from "./components/ServiceList";
import { StatsPanel } from "./components/StatsPanel";
import type { AllStats, ServerConfig, ServiceStatus } from "./lib/agentClient";
import { StatsSocket, fetchServices } from "./lib/agentClient";
import "./theme/retro.css";

export default function App() {
  const [config, setConfig] = useState<ServerConfig | null>(null);
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [stats, setStats] = useState<AllStats | null>(null);
  const [connected, setConnected] = useState(false);
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [servicesError, setServicesError] = useState<string | null>(null);
  const socketRef = useRef<StatsSocket | null>(null);

  useEffect(() => {
    if (!window.serverConfigApi) {
      setLoadingConfig(false);
      return;
    }
    window.serverConfigApi.get().then((saved) => {
      if (saved) setConfig(saved);
      setLoadingConfig(false);
    });
  }, []);

  useEffect(() => {
    if (!config) return;

    const socket = new StatsSocket(config, setStats, setConnected);
    socket.connect();
    socketRef.current = socket;

    const pollServices = () => {
      fetchServices(config)
        .then((svcs) => {
          setServices(svcs);
          setServicesError(null);
        })
        .catch((e) => setServicesError(e instanceof Error ? e.message : String(e)));
    };
    pollServices();
    const interval = window.setInterval(pollServices, 5000);

    return () => {
      socket.close();
      window.clearInterval(interval);
    };
  }, [config]);

  function handleConnect(newConfig: ServerConfig) {
    window.serverConfigApi?.set(newConfig);
    setConfig(newConfig);
  }

  function handleServiceChanged(updated: ServiceStatus) {
    setServices((prev) => prev.map((s) => (s.name === updated.name ? updated : s)));
  }

  if (loadingConfig) {
    return <div className="terminal-window">loading…</div>;
  }

  if (!config) {
    return (
      <>
        <div className="crt-scanlines" />
        <ConnectSetup onConnect={handleConnect} />
      </>
    );
  }

  return (
    <>
      <div className="crt-scanlines" />
      <div className="terminal-window">
        <div className="panel-row">
          <span>
            HOME SERVER MANAGER — {config.host}:{config.port}
          </span>
          <span className={`conn-status ${connected ? "ok" : "bad"}`}>
            {connected ? "● LINK OK" : "○ RECONNECTING…"}
          </span>
        </div>

        <StatsPanel stats={stats} />

        {servicesError ? (
          <div className="ascii-panel">
            <span className="panel-title">SERVICES</span>
            <div className="meter-bar crit">ERR: {servicesError}</div>
          </div>
        ) : (
          <ServiceList config={config} services={services} onChanged={handleServiceChanged} />
        )}
      </div>
    </>
  );
}
