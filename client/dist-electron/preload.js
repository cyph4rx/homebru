"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
electron_1.contextBridge.exposeInMainWorld("serverConfigApi", {
    get: () => electron_1.ipcRenderer.invoke("server-config:get"),
    set: (config) => electron_1.ipcRenderer.invoke("server-config:set", config),
});
