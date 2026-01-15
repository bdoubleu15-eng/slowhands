import './style.css'
import { APIClient } from './api';
import { EditorManager } from './editor';
import { UIManager } from './ui';
import { WSMessage } from './types';

// ============================================
// Application Initialization
// ============================================

const API_URL = 'http://127.0.0.1:8765';
const WS_URL = 'ws://127.0.0.1:8765/ws';

const editorContainer = document.getElementById('editor-container') as HTMLElement;
const editorManager = new EditorManager(editorContainer);

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
    async (path) => {
        try {
            const data = await apiClient.readFile(path);
            editorManager.updateFile(path, data.content);
            uiManager.addOutputLine(`[Open] ${path}`);
        } catch (e) {
            uiManager.addOutputLine(`[Error] Failed to open: ${path}`);
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
    }
);

const apiClient = new APIClient(
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
        const newWidth = Math.max(120, Math.min(400, e.clientX - 50));
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
