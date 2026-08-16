import { app, BrowserWindow, ipcMain } from "electron";
import path from "node:path";
import Store from "electron-store";

interface ServerConfig {
  host: string;
  port: number;
  token: string;
}

const store = new Store({
  defaults: { server: null as ServerConfig | null },
});

let mainWindow: BrowserWindow | null = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 640,
    backgroundColor: "#000000",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

const configStore = store as unknown as {
  get(key: "server"): ServerConfig | null;
  set(key: "server", value: ServerConfig): void;
};

ipcMain.handle("server-config:get", () => {
  return configStore.get("server");
});

ipcMain.handle("server-config:set", (_event, config: ServerConfig) => {
  configStore.set("server", config);
  return true;
});

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
