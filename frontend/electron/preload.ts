// See the Electron documentation for details on how to use preload scripts:
// https://www.electronjs.org/docs/latest/tutorial/process-model#preload-scripts
import { ipcRenderer } from 'electron'

// Since contextIsolation is false, we can directly expose to window
// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
declare global {
  interface Window {
    electronAPI: {
      minimize: () => Promise<void>
      maximize: () => Promise<void>
      close: () => Promise<void>
      openFileDialog: () => Promise<string | null>
      openFolderDialog: () => Promise<string | null>
      saveFileDialog: (defaultFileName?: string) => Promise<string | null>
      readFile: (filePath: string) => Promise<{ success: boolean; content?: string; path?: string; error?: string }>
      writeFile: (filePath: string, content: string) => Promise<{ success: boolean; error?: string }>
    }
  }
}

window.electronAPI = {
  // Window controls
  minimize: () => ipcRenderer.invoke('window:minimize'),
  maximize: () => ipcRenderer.invoke('window:maximize'),
  close: () => ipcRenderer.invoke('window:close'),
  
  // File dialogs
  openFileDialog: () => ipcRenderer.invoke('file:open-dialog'),
  openFolderDialog: () => ipcRenderer.invoke('file:open-folder-dialog'),
  saveFileDialog: (defaultFileName?: string) => ipcRenderer.invoke('file:save-dialog', defaultFileName),
  
  // File operations
  readFile: (filePath: string) => ipcRenderer.invoke('file:read-file', filePath),
  writeFile: (filePath: string, content: string) => ipcRenderer.invoke('file:write-file', filePath, content),
}

window.addEventListener('DOMContentLoaded', () => {
    const replaceText = (selector: string, text: string) => {
      const element = document.getElementById(selector)
      if (element) element.innerText = text
    }
  
    for (const type of ['chrome', 'node', 'electron']) {
      replaceText(`${type}-version`, process.versions[type as keyof NodeJS.ProcessVersions] as string)
    }
  })
