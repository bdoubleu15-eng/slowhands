import './style.css'
import { APIClient } from './api';
import { EditorManager } from './editor';
import { UIManager } from './ui';
import { WSMessage } from './types';
import { AudioCapture } from './audio';

// ============================================
// Global Error Handlers
// ============================================

// Track recent errors to avoid spam
const recentErrors: string[] = [];
const MAX_RECENT_ERRORS = 10;
const ERROR_DEDUP_WINDOW_MS = 5000;

function logError(source: string, message: string, details?: any): void {
    const errorKey = `${source}:${message}`;
    const now = Date.now();
    
    // Dedup: skip if we've seen this exact error recently
    if (recentErrors.includes(errorKey)) {
        return;
    }
    
    // Add to recent errors and clean up old ones
    recentErrors.push(errorKey);
    if (recentErrors.length > MAX_RECENT_ERRORS) {
        recentErrors.shift();
    }
    
    // Log to console
    console.error(`[${source}]`, message, details || '');
    
    // Try to show in UI if available (uiManager may not be initialized yet)
    try {
        const outputEl = document.getElementById('output');
        if (outputEl) {
            const errorLine = document.createElement('div');
            errorLine.className = 'output-line error';
            errorLine.textContent = `[Error] ${message}`;
            outputEl.appendChild(errorLine);
            outputEl.scrollTop = outputEl.scrollHeight;
        }
    } catch {
        // UI not ready, that's fine
    }
}

// Global error handler for uncaught errors
window.onerror = function(
    message: string | Event,
    source?: string,
    lineno?: number,
    colno?: number,
    error?: Error
): boolean {
    const errorMessage = typeof message === 'string' ? message : message.type;
    const location = source ? `${source}:${lineno}:${colno}` : 'unknown';
    
    logError('UncaughtError', `${errorMessage} at ${location}`, {
        stack: error?.stack,
        source,
        lineno,
        colno
    });
    
    // Return false to allow default error handling (logging to console)
    return false;
};

// Handler for unhandled promise rejections
window.onunhandledrejection = function(event: PromiseRejectionEvent): void {
    const reason = event.reason;
    let message: string;
    let stack: string | undefined;
    
    if (reason instanceof Error) {
        message = reason.message;
        stack = reason.stack;
    } else if (typeof reason === 'string') {
        message = reason;
    } else {
        message = String(reason);
    }
    
    logError('UnhandledRejection', message, { stack, reason });
    
    // Prevent the default handling (which would log to console again)
    event.preventDefault();
};

// ============================================
// Loading Overlay
// ============================================
let loadingOverlayTimeout: ReturnType<typeof setTimeout> | null = null;

function hideLoadingOverlay() {
    document.body.classList.remove('loading');
    if (loadingOverlayTimeout) {
        clearTimeout(loadingOverlayTimeout);
        loadingOverlayTimeout = null;
    }
}

// Safety: hide loading overlay after 5 seconds in case something goes wrong
loadingOverlayTimeout = setTimeout(hideLoadingOverlay, 5000);

// ============================================
// Application Initialization
// ============================================

const API_URL = 'http://127.0.0.1:8765';
const WS_URL = 'ws://127.0.0.1:8765/ws';

const editorContainer = document.getElementById('editor-container') as HTMLElement;
const tabBarElement = document.getElementById('tab-bar') as HTMLElement;
const editorManager = new EditorManager(editorContainer);

// Set up tab bar
editorManager.setTabBarElement(tabBarElement);

// Declare apiClient variable first (will be initialized after uiManager)
let apiClient: APIClient;

const uiManager = new UIManager(
    // onSendMessage
    (message) => {
        const correlationId = apiClient.generateCorrelationId();
        apiClient.send({ type: 'chat', content: message, correlation_id: correlationId });
        uiManager.addOutputLine(`> ${message}`);
        uiManager.setThinking(true); // Show spinner immediately
    },
    // onStopAgent
    () => {
        const correlationId = apiClient.generateCorrelationId();
        apiClient.send({ type: 'stop', correlation_id: correlationId });
        uiManager.addOutputLine('Stopping...');
    },
    // onOpenFile
    async (filePath) => {
        try {
            // Check if we can open more tabs
            if (!editorManager.canOpenMoreTabs()) {
                uiManager.addOutputLine(`[Error] Maximum ${editorManager.MAX_TABS} tabs open. Close a tab first.`);
                return;
            }
            
            // Try to read via Electron first (for files outside workspace)
            // @ts-ignore
            const electronResult = await window.electronAPI?.readFile(filePath);
            if (electronResult?.success) {
                editorManager.openFile(filePath, electronResult.content || '');
                uiManager.addOutputLine(`[Open] ${filePath}`);
                return;
            }
            
            // Fallback to API (for workspace files)
            const data = await apiClient.readFile(filePath);
            editorManager.openFile(filePath, data.content);
            uiManager.addOutputLine(`[Open] ${filePath}`);
        } catch (e) {
            uiManager.addOutputLine(`[Error] Failed to open: ${filePath}`);
        }
    },
    // onOpenFolder
    async () => {
        try {
            // @ts-ignore
            const folderPath = await window.electronAPI?.openFolderDialog();
            if (folderPath) {
                uiManager.addOutputLine(`[Open Folder] ${folderPath}`);
                
                // Call backend to set workspace
                const result = await apiClient.openWorkspace(folderPath);
                uiManager.renderFileTree(result.files);
                uiManager.addOutputLine(`[Workspace] Opened: ${result.workspace}`);
            }
        } catch (error: any) {
            console.error('Failed to open folder:', error);
            uiManager.addOutputLine(`[Error] Failed to open folder: ${error.message}`);
        }
    },
    // onTogglePause
    () => {
        const isPaused = editorManager.togglePause();
        uiManager.updatePauseButton(isPaused, editorManager.getIsStreaming());
        uiManager.addOutputLine(isPaused ? '[Pause] Paused streaming' : '[Resume] Resumed streaming');
    },
    // onSkipStreaming
    () => {
        if (editorManager.getIsStreaming()) {
            editorManager.stopStreaming();
            uiManager.updatePauseButton(false, false);
            uiManager.addOutputLine('[Skip] Skipped to end');
        }
    },
    // onSaveFile
    async (filePath: string, content: string) => {
        try {
            // @ts-ignore
            const result = await window.electronAPI?.writeFile(filePath, content);
            if (result?.success) {
                // Mark the current tab as clean
                editorManager.markCurrentTabClean();
                // Refresh file browser to show new file
                refreshFileBrowser();
            } else {
                throw new Error(result?.error || 'Failed to save file');
            }
        } catch (error: any) {
            throw new Error(`Failed to save file: ${error.message}`);
        }
    },
    // onGetCurrentFile
    () => {
        return {
            path: editorManager.getCurrentFilePath(),
            content: editorManager.getCurrentContent()
        };
    }
);

apiClient = new APIClient(
    API_URL,
    WS_URL,
    // onMessage
    (data: WSMessage) => handleAgentMessage(data),
    // onStatusChange
    (connected) => {
        uiManager.updateConnectionStatus(connected);
        if (connected) refreshFileBrowser();
    },
    // onLog
    (text) => uiManager.addOutputLine(text)
);

// Link editor manager to UI manager
editorManager.onFileChanged = (path) => uiManager.updateFileNameDisplay(path);

// Hide loading overlay now that UI is ready
hideLoadingOverlay();

// ============================================
// Push-to-Talk Audio Capture
// ============================================

const audioCapture = new AudioCapture({ sampleRate: 16000, channels: 1 });

// Set up audio capture callbacks
audioCapture.setOnStateChange((isRecording) => {
    uiManager.setRecording(isRecording);
    if (isRecording) {
        uiManager.addOutputLine('[PTT] Recording...');
    }
});

audioCapture.setOnAudioData(async (result) => {
    uiManager.addOutputLine(`[PTT] Captured ${result.duration.toFixed(1)}s of audio, transcribing...`);
    uiManager.setTranscribing(true);

    // Convert blob to base64
    const arrayBuffer = await result.blob.arrayBuffer();
    const base64 = btoa(
        new Uint8Array(arrayBuffer).reduce((data, byte) => data + String.fromCharCode(byte), '')
    );

    // Send to backend for transcription
    apiClient.send({
        type: 'transcribe',
        audio_data: base64,
        correlation_id: apiClient.generateCorrelationId()
    });
});

audioCapture.setOnError((error) => {
    uiManager.addOutputLine(`[PTT Error] ${error.message}`);
    uiManager.setRecording(false);
    uiManager.setTranscribing(false);
});

// Listen for PTT events from Electron
// @ts-ignore
if (window.electronAPI?.onPttDown) {
    // @ts-ignore
    window.electronAPI.onPttDown(() => {
        if (!audioCapture.isRecording()) {
            audioCapture.startRecording().catch((err) => {
                uiManager.addOutputLine(`[PTT Error] Failed to start recording: ${err.message}`);
            });
        }
    });
}

// @ts-ignore
if (window.electronAPI?.onPttUp) {
    // @ts-ignore
    window.electronAPI.onPttUp(() => {
        if (audioCapture.isRecording()) {
            audioCapture.stopRecording();
        }
    });
}

// Request microphone permission on startup (non-blocking)
if (AudioCapture.isSupported()) {
    audioCapture.requestPermission().then((granted) => {
        if (granted) {
            uiManager.addOutputLine('[PTT] Microphone permission granted');
        } else {
            uiManager.addOutputLine('[PTT] Microphone permission denied - PTT will not work');
        }
    });
} else {
    uiManager.addOutputLine('[PTT] Audio recording not supported in this browser');
}

function handleAgentMessage(data: WSMessage) {
    // Hide thinking indicator when we get any response
    uiManager.setThinking(false);
    
    switch (data.type) {
        case 'step':
            // Show thinking again if this is a thinking step (more coming)
            if (data.phase === 'think') {
                uiManager.setThinking(true);
            }
            
            if (data.file_op) {
                const { action, path, content } = data.file_op;
                uiManager.addOutputLine(`[${action === 'write' ? 'Write' : 'Read'}] ${action}: ${path}`);
                if (action === 'write') {
                    const speed = 12 * Math.min(2, 1 + content.length / 2000);
                    editorManager.streamContent(path, content, speed).then(() => {
                        refreshFileBrowser();
                        uiManager.updatePauseButton(false, false);
                    });
                } else {
                    editorManager.updateFile(path, content);
                }
            }
            if (data.phase !== 'respond') {
                const phase = data.phase === 'act' ? '[Act]' : '[Think]';
                const content = data.content.length > 200 ? data.content.substring(0, 200) + '...' : data.content;
                uiManager.addOutputLine(`${phase} ${content}`);
            }
            break;
        case 'complete':
            uiManager.setThinking(false);
            const content = data.content.length > 500 ? data.content.substring(0, 500) + '...' : data.content;
            uiManager.addOutputLine(`[Complete] ${content}`);
            break;
        case 'stopped':
            uiManager.setThinking(false);
            uiManager.addOutputLine('[Stopped]');
            break;
        case 'error':
            uiManager.setThinking(false);
            uiManager.addOutputLine(`[Error] ${data.content}`);
            break;
        case 'file_content':
            editorManager.updateFile(data.path, data.content);
            uiManager.addOutputLine(`[Open] ${data.path}`);
            break;
        case 'server_shutdown':
            uiManager.setThinking(false);
            uiManager.addOutputLine('[Server] Server is shutting down...');
            uiManager.updateConnectionStatus(false);
            break;
        case 'transcribing':
            // Show transcription status
            if (data.status === 'started') {
                uiManager.setTranscribing(true);
            }
            break;
        case 'transcription_result':
            uiManager.setTranscribing(false);
            uiManager.setRecording(false);
            if (data.text && data.text.trim()) {
                const transcribedText = data.text.trim();
                
                // Insert into SlowHands input
                uiManager.insertIntoInput(transcribedText);
                uiManager.addOutputLine(`[PTT] Transcribed: "${transcribedText}"`);
                
                // Global text injection (system-wide)
                // @ts-ignore
                if (window.electronAPI?.injectTextGlobally) {
                    // @ts-ignore
                    window.electronAPI.injectTextGlobally(transcribedText).catch((err: Error) => {
                        console.error('[PTT] Global injection failed:', err);
                        uiManager.addOutputLine(`[PTT] Global injection failed: ${err.message}`);
                    });
                }
            } else {
                uiManager.addOutputLine('[PTT] No speech detected');
            }
            break;
    }
}

async function refreshFileBrowser() {
    const files = await apiClient.fetchFiles();
    uiManager.renderFileTree(files);
}

// ============================================
// Resizable Sidebar & Panels
// ============================================

const resizeHandle = document.getElementById('resize-handle');
const appContainer = document.getElementById('app');
let isResizing = false;

resizeHandle?.addEventListener('mousedown', (e) => {
    isResizing = true;
    resizeHandle.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    e.preventDefault();
});

const agentResizeHandle = document.getElementById('agent-resize-handle');
const agentPanel = document.getElementById('agent-panel');
let isResizingAgent = false;

agentResizeHandle?.addEventListener('mousedown', (e) => {
    isResizingAgent = true;
    agentResizeHandle.classList.add('dragging');
    document.body.style.cursor = 'row-resize';
    e.preventDefault();
});

document.addEventListener('mousemove', (e) => {
    if (isResizing && appContainer) {
        // Activity bar is 54px wide
        const newWidth = Math.max(120, Math.min(400, e.clientX - 54));
        appContainer.style.setProperty('--sidebar-width', `${newWidth}px`);
        editorManager.layout();
    }
    if (isResizingAgent && agentPanel) {
        const rect = agentPanel.parentElement?.getBoundingClientRect();
        if (rect) {
            const newHeight = Math.max(80, Math.min(300, rect.bottom - e.clientY));
            agentPanel.style.height = `${newHeight}px`;
        }
    }
});

document.addEventListener('mouseup', () => {
    isResizing = false;
    isResizingAgent = false;
    resizeHandle?.classList.remove('dragging');
    agentResizeHandle?.classList.remove('dragging');
    document.body.style.cursor = '';
});

// ============================================
// Keyboard Shortcuts
// ============================================

document.addEventListener('keydown', (e) => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
    
    if (e.key === ' ' && editorManager.getIsStreaming()) {
        e.preventDefault();
        const isPaused = editorManager.togglePause();
        uiManager.updatePauseButton(isPaused, true);
        uiManager.addOutputLine(isPaused ? '[Pause] Paused streaming' : '[Resume] Resumed streaming');
    }
    
    if (e.key === 'Escape' && editorManager.getIsStreaming()) {
        editorManager.stopStreaming();
        uiManager.updatePauseButton(false, false);
        uiManager.addOutputLine('[Skip] Skipped to end');
    }
});

// Start connection
setTimeout(() => apiClient.connect(), 500);
