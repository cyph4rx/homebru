import { contextBridge, ipcRenderer } from "electron";

export interface ServerConfig {
  host: string;
  port: number;
  token: string;
}

contextBridge.exposeInMainWorld("serverConfigApi", {
  get: (): Promise<ServerConfig | null> => ipcRenderer.invoke("server-config:get"),
  set: (config: ServerConfig): Promise<boolean> => ipcRenderer.invoke("server-config:set", config),
});
