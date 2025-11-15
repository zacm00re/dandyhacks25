const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

let pythonProcess = null;
let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });
  // mainWindow.setMenu(null);
  // Load from Vite dev server in development, or from built files in production
  const isDev = process.env.NODE_ENV === "development" || !app.isPackaged;
  mainWindow.webContents.openDevTools();
  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

function startPythonBackend() {
  const pythonScript = path.join(__dirname, "backend", "main.py");

  pythonProcess = spawn("python", [pythonScript]);

  pythonProcess.stdout.on("data", (data) => {
    console.log(`Python: ${data}`);
  });

  pythonProcess.stderr.on("data", (data) => {
    console.error(`Python Error: ${data}`);
  });

  pythonProcess.on("close", (code) => {
    console.log(`Python process exited with code ${code}`);
  });
}

app.whenReady().then(() => {
  startPythonBackend();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("quit", () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});

// IPC handlers for communication with renderer
ipcMain.handle("ping-python", async () => {
  try {
    const response = await fetch("http://localhost:8000/ping");
    const data = await response.json();
    return data;
  } catch (error) {
    return { error: error.message };
  }
});
