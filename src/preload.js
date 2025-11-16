const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
  pingPython: () => ipcRenderer.invoke('ping-python'),
});
