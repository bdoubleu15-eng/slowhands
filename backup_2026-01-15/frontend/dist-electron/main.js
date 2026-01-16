"use strict";
const electron = require("electron");
const path = require("node:path");
process.env.DIST = path.join(__dirname, "../dist");
process.env.PUBLIC = electron.app.isPackaged ? process.env.DIST : path.join(process.env.DIST, "../public");
const publicDir = process.env.PUBLIC || "";
const distDir = process.env.DIST || "";
let win;
const VITE_DEV_SERVER_URL = process.env["VITE_DEV_SERVER_URL"];
function createWindow() {
  win = new electron.BrowserWindow({
    width: 1200,
    height: 800,
    title: "SlowHands",
    backgroundColor: "#ffffff",
    // Light theme background
    icon: path.join(publicDir, "electron-vite.svg"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: true,
      contextIsolation: false
    },
    frame: false,
    // Frameless for custom title bar
    titleBarStyle: "hidden",
    titleBarOverlay: {
      color: "#f0f0f0",
      symbolColor: "#1e1e1e"
    }
  });
  win.webContents.on("did-finish-load", () => {
    win?.webContents.send("main-process-message", (/* @__PURE__ */ new Date()).toLocaleString());
  });
  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL);
  } else {
    win.loadFile(path.join(distDir, "index.html"));
  }
}
electron.app.on("window-all-closed", () => {
  win = null;
  if (process.platform !== "darwin") electron.app.quit();
});
electron.app.whenReady().then(createWindow);
