import { app, BrowserWindow, dialog, ipcMain } from 'electron'
import path from 'node:path'
import { execSync } from 'child_process'
import { existsSync, writeFileSync, mkdirSync, readFileSync } from 'fs'

// The built directory structure
//
// ├─┬─ dist
// │ ├─ index.html
// │ ├─ assets
// │ └── index.js
// ├─┬─ dist-electron
// │ ├─ main.js
// │ └── preload.js
//
process.env.DIST = path.join(__dirname, '../dist')
process.env.PUBLIC = app.isPackaged ? process.env.DIST : path.join(process.env.DIST, '../public')

// Ensure paths are strings to satisfy TS
const publicDir = process.env.PUBLIC || ''
const distDir = process.env.DIST || ''

let win: BrowserWindow | null
// 🚧 Use ['ENV_NAME'] avoid vite:define plugin - Vite@2.x
const VITE_DEV_SERVER_URL = process.env['VITE_DEV_SERVER_URL']

// WSL path conversion utilities
function isWSL(): boolean {
  try {
    if (process.platform !== 'linux') return false
    const version = require('fs').readFileSync('/proc/version', 'utf8')
    return version.toLowerCase().includes('microsoft') || version.toLowerCase().includes('wsl')
  } catch {
    return false
  }
}

function wslToWindowsPath(wslPath: string): string {
  if (!isWSL()) return wslPath
  
  try {
    // Use wslpath to convert WSL path to Windows path
    const result = execSync(`wslpath -w "${wslPath}"`, { encoding: 'utf8' }).trim()
    return result
  } catch (error) {
    console.error('Failed to convert WSL path:', error)
    // Fallback: try to construct Windows path manually
    // Format: \\wsl$\<distro>\<path>
    const distro = process.env.WSL_DISTRO_NAME || 'Ubuntu'
    const windowsPath = wslPath.replace(/^\//, '').replace(/\//g, '\\')
    return `\\\\wsl$\\${distro}\\${windowsPath}`
  }
}

function getDefaultDirectory(): string {
  try {
    const cwd = process.cwd()
    // Check if we're in a working directory (not just home)
    if (cwd !== process.env.HOME && existsSync(cwd)) {
      return wslToWindowsPath(cwd)
    }
    // Otherwise use WSL home
    const home = process.env.HOME || '/home/' + process.env.USER
    return wslToWindowsPath(home)
  } catch (error) {
    console.error('Failed to get default directory:', error)
    return wslToWindowsPath(process.env.HOME || '/home')
  }
}

function createWindow() {
  win = new BrowserWindow({
    width: 1200,
    height: 800,
    title: "SlowHands",
    backgroundColor: '#ffffff',  // Light theme background
    icon: path.join(publicDir, 'electron-vite.svg'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: true,
      contextIsolation: false,
    },
    frame: false,  // Frameless for custom title bar
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#f0f0f0',
      symbolColor: '#1e1e1e'
    }
  })

  // Test active push message to Renderer-process.
  win.webContents.on('did-finish-load', () => {
    win?.webContents.send('main-process-message', (new Date).toLocaleString())
  })

  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL)
  } else {
    win.loadFile(path.join(distDir, 'index.html'))
  }
}

// IPC Handlers for window controls
ipcMain.handle('window:minimize', () => {
  win?.minimize()
})

ipcMain.handle('window:maximize', () => {
  if (win?.isMaximized()) {
    win.unmaximize()
  } else {
    win?.maximize()
  }
})

ipcMain.handle('window:close', () => {
  win?.close()
})

// IPC Handlers for file dialogs
ipcMain.handle('file:open-folder-dialog', async () => {
  if (!win) return null
  
  const defaultPath = getDefaultDirectory()
  const result = await dialog.showOpenDialog(win, {
    title: 'Open Folder',
    defaultPath: defaultPath,
    properties: ['openDirectory']
  })
  
  if (result.canceled || result.filePaths.length === 0) {
    return null
  }
  
  // Convert Windows path back to WSL path if needed
  let folderPath = result.filePaths[0]
  if (isWSL() && folderPath.startsWith('\\\\wsl$\\')) {
    try {
      folderPath = execSync(`wslpath -u "${folderPath}"`, { encoding: 'utf8' }).trim()
    } catch (error) {
      console.error('Failed to convert Windows path to WSL:', error)
    }
  }
  
  return folderPath
})

ipcMain.handle('file:open-dialog', async () => {
  if (!win) return null
  
  const defaultPath = getDefaultDirectory()
  const result = await dialog.showOpenDialog(win, {
    title: 'Open File',
    defaultPath: defaultPath,
    properties: ['openFile'],
    filters: [
      { name: 'All Files', extensions: ['*'] },
      { name: 'Text Files', extensions: ['txt', 'md', 'json', 'yaml', 'yml'] },
      { name: 'Code Files', extensions: ['js', 'ts', 'jsx', 'tsx', 'py', 'java', 'cpp', 'c', 'h', 'hpp', 'rs', 'go', 'rb', 'php'] },
      { name: 'Web Files', extensions: ['html', 'htm', 'css', 'scss', 'less', 'xml'] },
      { name: 'Shell Scripts', extensions: ['sh', 'bash', 'zsh'] },
    ]
  })
  
  if (result.canceled || result.filePaths.length === 0) {
    return null
  }
  
  // Convert Windows path back to WSL path if needed
  let filePath = result.filePaths[0]
  if (isWSL() && filePath.startsWith('\\\\wsl$\\')) {
    try {
      filePath = execSync(`wslpath -u "${filePath}"`, { encoding: 'utf8' }).trim()
    } catch (error) {
      console.error('Failed to convert Windows path to WSL:', error)
    }
  }
  
  return filePath
})

ipcMain.handle('file:save-dialog', async (_, defaultFileName?: string) => {
  if (!win) return null
  
  const defaultPath = getDefaultDirectory()
  const defaultFile = defaultFileName ? path.join(defaultPath, defaultFileName) : defaultPath
  
  const result = await dialog.showSaveDialog(win, {
    title: 'Save File',
    defaultPath: defaultFile,
    filters: [
      { name: 'All Files', extensions: ['*'] },
      { name: 'Text Files', extensions: ['txt', 'md', 'json', 'yaml', 'yml'] },
      { name: 'Code Files', extensions: ['js', 'ts', 'jsx', 'tsx', 'py', 'java', 'cpp', 'c', 'h', 'hpp', 'rs', 'go', 'rb', 'php'] },
      { name: 'Web Files', extensions: ['html', 'htm', 'css', 'scss', 'less', 'xml'] },
      { name: 'Shell Scripts', extensions: ['sh', 'bash', 'zsh'] },
    ]
  })
  
  if (result.canceled || !result.filePath) {
    return null
  }
  
  // Convert Windows path back to WSL path if needed
  let filePath = result.filePath
  if (isWSL() && filePath.startsWith('\\\\wsl$\\')) {
    try {
      filePath = execSync(`wslpath -u "${filePath}"`, { encoding: 'utf8' }).trim()
    } catch (error) {
      console.error('Failed to convert Windows path to WSL:', error)
    }
  }
  
  return filePath
})

ipcMain.handle('file:read-file', async (_, filePath: string) => {
  try {
    if (!existsSync(filePath)) {
      return { success: false, error: 'File not found' }
    }
    
    const content = readFileSync(filePath, 'utf8')
    return { success: true, content, path: filePath }
  } catch (error: any) {
    console.error('Failed to read file:', error)
    return { success: false, error: error.message }
  }
})

ipcMain.handle('file:write-file', async (_, filePath: string, content: string) => {
  try {
    // Ensure directory exists
    const dir = path.dirname(filePath)
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true })
    }
    
    // Write the file
    writeFileSync(filePath, content, 'utf8')
    return { success: true }
  } catch (error: any) {
    console.error('Failed to write file:', error)
    return { success: false, error: error.message }
  }
})

app.on('window-all-closed', () => {
  win = null
  if (process.platform !== 'darwin') app.quit()
})

app.whenReady().then(() => {
  createWindow()
})
