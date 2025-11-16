export interface IElectronAPI {
  pingPython: () => Promise<any>;
}

declare global {
  interface Window {
    electron: IElectronAPI;
  }
}
