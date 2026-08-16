"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const node_path_1 = __importDefault(require("node:path"));
const electron_store_1 = __importDefault(require("electron-store"));
const store = new electron_store_1.default({
    defaults: { server: null },
});
let mainWindow = null;
function createWindow() {
    mainWindow = new electron_1.BrowserWindow({
        width: 900,
        height: 640,
        backgroundColor: "#000000",
        autoHideMenuBar: true,
        webPreferences: {
            preload: node_path_1.default.join(__dirname, "preload.js"),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });
    if (process.env.VITE_DEV_SERVER_URL) {
        mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
    }
    else {
        mainWindow.loadFile(node_path_1.default.join(__dirname, "../dist/index.html"));
    }
}
const configStore = store;
electron_1.ipcMain.handle("server-config:get", () => {
    return configStore.get("server");
});
electron_1.ipcMain.handle("server-config:set", (_event, config) => {
    configStore.set("server", config);
    return true;
});
electron_1.app.whenReady().then(createWindow);
electron_1.app.on("window-all-closed", () => {
    if (process.platform !== "darwin") {
        electron_1.app.quit();
    }
});
electron_1.app.on("activate", () => {
    if (electron_1.BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});
