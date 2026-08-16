/// <reference types="vite/client" />

interface ServerConfig {
  host: string;
  port: number;
  token: string;
}

interface Window {
  serverConfigApi?: {
    get: () => Promise<ServerConfig | null>;
    set: (config: ServerConfig) => Promise<boolean>;
  };
}
