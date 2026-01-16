import { app, BrowserWindow, dialog, ipcMain } from 'electron'
import path from 'node:path'
import { execSync, spawn, ChildProcess } from 'child_process'
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
let pttProcess: ChildProcess | null = null
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

function getPTTHelperPath(): string {
  // Get the project root directory
  const projectRoot = process.cwd()
  const helperPath = path.join(projectRoot, 'tools', 'ptt-helper', 'ptt_helper.py')
  
  // Convert to Windows path if running in WSL
  if (isWSL()) {
    return wslToWindowsPath(helperPath)
  }
  
  return helperPath
}

function startPTTHelper() {
  // Only start on Windows or WSL
  if (process.platform !== 'win32' && !isWSL()) {
    console.log('[PTT] Not running on Windows/WSL, skipping PTT helper')
    return
  }

  // Don't start if already running
  if (pttProcess && !pttProcess.killed) {
    console.log('[PTT] Helper already running')
    return
  }

  try {
    const helperPath = getPTTHelperPath()
    console.log(`[PTT] Starting helper: ${helperPath}`)

    // Spawn Python process to run the PTT helper
    // Use 'python' command (Windows will find it in PATH)
    pttProcess = spawn('python', [helperPath], {
      shell: true,
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false
    })

    let buffer = ''

    pttProcess.stdout?.on('data', (data: Buffer) => {
      buffer += data.toString()
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // Keep incomplete line in buffer

      for (const line of lines) {
        const trimmed = line.trim()
        if (trimmed === 'PTT_DOWN') {
          console.log('[PTT] Key pressed')
          win?.webContents.send('ptt-down')
        } else if (trimmed === 'PTT_UP') {
          console.log('[PTT] Key released')
          win?.webContents.send('ptt-up')
        } else if (trimmed === 'PTT_READY') {
          console.log('[PTT] Helper ready')
        } else if (trimmed.startsWith('PTT_ERROR:')) {
          console.error(`[PTT] Error: ${trimmed}`)
        } else if (trimmed === 'PTT_EXIT') {
          console.log('[PTT] Helper exited')
        }
      }
    })

    pttProcess.stderr?.on('data', (data: Buffer) => {
      console.error(`[PTT] stderr: ${data.toString()}`)
    })

    pttProcess.on('error', (error) => {
      console.error('[PTT] Failed to start helper:', error)
      pttProcess = null
    })

    pttProcess.on('exit', (code, signal) => {
      console.log(`[PTT] Helper exited with code ${code}, signal ${signal}`)
      pttProcess = null
      
      // Restart after a delay if it crashed unexpectedly
      if (code !== 0 && code !== null) {
        console.log('[PTT] Helper crashed, will restart in 2 seconds...')
        setTimeout(() => {
          if (win && !win.isDestroyed()) {
            startPTTHelper()
          }
        }, 2000)
      }
    })

  } catch (error) {
    console.error('[PTT] Failed to start helper:', error)
    pttProcess = null
  }
}

function stopPTTHelper() {
  if (pttProcess && !pttProcess.killed) {
    console.log('[PTT] Stopping helper')
    pttProcess.kill()
    pttProcess = null
  }
}

function getTextInjectorPath(): string {
  // Get the project root directory
  const projectRoot = process.cwd()
  const injectorPath = path.join(projectRoot, 'tools', 'ptt-helper', 'text_injector.py')
  
  // Convert to Windows path if running in WSL
  if (isWSL()) {
    return wslToWindowsPath(injectorPath)
  }
  
  return injectorPath
}

async function injectTextGlobally(text: string): Promise<boolean> {
  // Only work on Windows or WSL
  if (process.platform !== 'win32' && !isWSL()) {
    console.log('[PTT] Not running on Windows/WSL, skipping global injection')
    return false
  }

  if (!text || !text.trim()) {
    return false
  }

  try {
    const injectorPath = getTextInjectorPath()
    console.log(`[PTT] Injecting text globally: ${text.substring(0, 50)}...`)

    // Spawn text injector and send text via stdin
    const injectorProcess = spawn('python', [injectorPath], {
      shell: true,
      stdio: ['pipe', 'pipe', 'pipe'],
      detached: false
    })

    // Send text to injector
    injectorProcess.stdin?.write(text + '\n')
    injectorProcess.stdin?.end()

    // Wait for completion (with timeout)
    return new Promise((resolve) => {
      let output = ''
      let errorOutput = ''

      injectorProcess.stdout?.on('data', (data: Buffer) => {
        output += data.toString()
      })

      injectorProcess.stderr?.on('data', (data: Buffer) => {
        errorOutput += data.toString()
      })

      injectorProcess.on('exit', (code) => {
        if (code === 0 || output.includes('INJECTED')) {
          console.log('[PTT] Text injected successfully')
          resolve(true)
        } else {
          console.error(`[PTT] Injection failed: ${errorOutput || output}`)
          resolve(false)
        }
      })

      // Timeout after 5 seconds
      setTimeout(() => {
        if (!injectorProcess.killed) {
          injectorProcess.kill()
          console.error('[PTT] Injection timeout')
          resolve(false)
        }
      }, 5000)
    })

  } catch (error) {
    console.error('[PTT] Failed to inject text:', error)
    return false
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

// IPC Handler for global text injection
ipcMain.handle('ptt:inject-text-globally', async (_, text: string) => {
  const success = await injectTextGlobally(text)
  return { success }
})

app.on('window-all-closed', () => {
  stopPTTHelper()
  win = null
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  stopPTTHelper()
})

app.whenReady().then(() => {
  createWindow()
  // Start PTT helper after window is created
  setTimeout(() => {
    startPTTHelper()
  }, 1000) // Small delay to ensure window is ready
})
