import './style.css'
import * as monaco from 'monaco-editor'
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import jsonWorker from 'monaco-editor/esm/vs/language/json/json.worker?worker'
import cssWorker from 'monaco-editor/esm/vs/language/css/css.worker?worker'
import htmlWorker from 'monaco-editor/esm/vs/language/html/html.worker?worker'
import tsWorker from 'monaco-editor/esm/vs/language/typescript/ts.worker?worker'

self.MonacoEnvironment = {
  getWorker(_, label) {
    if (label === 'json') {
      return new jsonWorker()
    }
    if (label === 'css' || label === 'scss' || label === 'less') {
      return new cssWorker()
    }
    if (label === 'html' || label === 'handlebars' || label === 'razor') {
      return new htmlWorker()
    }
    if (label === 'typescript' || label === 'javascript') {
      return new tsWorker()
    }
    return new editorWorker()
  }
}

const editorContainer = document.getElementById('editor-container') as HTMLElement;

const editor = monaco.editor.create(editorContainer, {
  value: [
    '// Welcome to SlowHands',
    '// Your AI coding assistant is ready.',
    '',
    'function hello() {',
    '\treturn "Hello from SlowHands!";',
    '}'
  ].join('\n'),
  language: 'typescript',
  theme: 'vs',
  automaticLayout: true,
  minimap: { enabled: true },
  fontSize: 14,
  fontFamily: "'Fira Code', 'Cascadia Code', 'Consolas', monospace",
  scrollBeyondLastLine: false,
  renderLineHighlight: 'all',
  cursorBlinking: 'smooth',
  smoothScrolling: true,
});

// ============================================
// Editor File Handling
// ============================================
let currentFilePath: string | null = null;

// Map file extensions to Monaco language IDs
function getLanguageFromPath(filePath: string): string {
  const ext = filePath.split('.').pop()?.toLowerCase() || '';
  const languageMap: Record<string, string> = {
    'js': 'javascript',
    'jsx': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'py': 'python',
    'json': 'json',
    'html': 'html',
    'htm': 'html',
    'css': 'css',
    'scss': 'scss',
    'less': 'less',
    'md': 'markdown',
    'yaml': 'yaml',
    'yml': 'yaml',
    'xml': 'xml',
    'sql': 'sql',
    'sh': 'shell',
    'bash': 'shell',
    'rs': 'rust',
    'go': 'go',
    'java': 'java',
    'c': 'c',
    'cpp': 'cpp',
    'h': 'c',
    'hpp': 'cpp',
    'rb': 'ruby',
    'php': 'php',
    'txt': 'plaintext',
  };
  return languageMap[ext] || 'plaintext';
}

// Streaming state
let isStreaming = false;
let isPaused = false;
let streamingAbortController: AbortController | null = null;
let streamingFilePath: string | null = null;
let pendingStreamContent: string | null = null;
let currentStreamingContent: string | null = null; // Full content being streamed

// Pause/resume streaming
function togglePause(): void {
  if (!isStreaming) return;
  isPaused = !isPaused;
  updatePauseButton();
  if (isPaused) {
    addOutputLine('⏸ Paused streaming');
  } else {
    addOutputLine('▶ Resumed streaming');
  }
}

function pauseStreaming(): void {
  if (isStreaming && !isPaused) {
    isPaused = true;
    updatePauseButton();
    addOutputLine('⏸ Paused streaming');
  }
}

function resumeStreaming(): void {
  if (isStreaming && isPaused) {
    isPaused = false;
    updatePauseButton();
    addOutputLine('▶ Resumed streaming');
  }
}

function updatePauseButton(): void {
  const pauseBtn = document.getElementById('pause-btn');
  if (pauseBtn) {
    pauseBtn.textContent = isPaused ? '▶' : '⏸';
    pauseBtn.title = isPaused ? 'Resume streaming (Space)' : 'Pause streaming (Space)';
  }
}

// Update editor with file content (instant)
function updateEditorWithFile(filePath: string, content: string) {
  currentFilePath = filePath;
  const language = getLanguageFromPath(filePath);
  
  // Update editor content and language
  const model = editor.getModel();
  if (model) {
    monaco.editor.setModelLanguage(model, language);
    editor.setValue(content);
  }
  
  // Update filename display in UI
  updateFileNameDisplay(filePath);
  
  console.log(`Editor updated: ${filePath} (${language})`);
}

// Stream content character-by-character with typing effect
async function streamToEditor(filePath: string, content: string, charsPerSecond: number = 60) {
  // If already streaming this file, save content for later (will be shown when current stream ends)
  if (isStreaming && streamingFilePath === filePath) {
    pendingStreamContent = content;
    console.log(`Already streaming ${filePath}, queued update`);
    return;
  }
  
  // Cancel any existing stream for a DIFFERENT file
  if (streamingAbortController) {
    streamingAbortController.abort();
  }
  streamingAbortController = new AbortController();
  const signal = streamingAbortController.signal;
  
  currentFilePath = filePath;
  streamingFilePath = filePath;
  const language = getLanguageFromPath(filePath);
  
  // Set language and clear editor
  const model = editor.getModel();
  if (model) {
    monaco.editor.setModelLanguage(model, language);
    editor.setValue('');
  }
  
  // Update filename display
  updateFileNameDisplay(filePath);
  
  isStreaming = true;
  isPaused = false;
  pendingStreamContent = null;
  currentStreamingContent = content; // Save full content for skip functionality
  updatePauseButton();
  const delayMs = 1000 / charsPerSecond;
  let currentContent = '';
  
  // Stream character by character
  for (let i = 0; i < content.length; i++) {
    // Check for abort
    if (signal.aborted) {
      console.log('Stream aborted');
      break;
    }
    
    // Wait while paused (check every 100ms)
    while (isPaused && !signal.aborted) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    // Check abort again after pause
    if (signal.aborted) break;
    
    currentContent += content[i];
    editor.setValue(currentContent);
    
    // Move cursor to end
    const lineCount = model?.getLineCount() || 1;
    const lastLineLength = model?.getLineLength(lineCount) || 0;
    editor.setPosition({ lineNumber: lineCount, column: lastLineLength + 1 });
    editor.revealLine(lineCount);
    
    // Variable delay - faster for whitespace, slower for code
    const char = content[i];
    let charDelay = delayMs;
    if (char === ' ' || char === '\t') {
      charDelay = delayMs * 0.3; // Faster for spaces
    } else if (char === '\n') {
      charDelay = delayMs * 2; // Pause at newlines
    }
    
    await new Promise(resolve => setTimeout(resolve, charDelay));
  }
  
  // Reset state when streaming ends
  isPaused = false;
  isStreaming = false;
  streamingFilePath = null;
  currentStreamingContent = null;
  updatePauseButton();
  console.log(`Finished streaming: ${filePath}`);
  
  // If there's pending content (newer version of file), show it instantly
  if (pendingStreamContent !== null) {
    console.log(`Showing pending content for ${filePath}`);
    editor.setValue(pendingStreamContent);
    pendingStreamContent = null;
  }
}

// Stop current streaming and show full content
function stopStreaming() {
  if (streamingAbortController) {
    streamingAbortController.abort();
    streamingAbortController = null;
  }
  
  // Show full content when skipped
  if (currentStreamingContent !== null) {
    editor.setValue(currentStreamingContent);
    currentStreamingContent = null;
  }
  
  // Show pending content if any (newer version)
  if (pendingStreamContent !== null) {
    editor.setValue(pendingStreamContent);
    pendingStreamContent = null;
  }
  
  isStreaming = false;
  isPaused = false;
  streamingFilePath = null;
  updatePauseButton();
}

// Update the filename in the title bar or status
function updateFileNameDisplay(filePath: string) {
  // Update the app title to show current file
  const appTitle = document.querySelector('.app-title');
  if (appTitle) {
    const fileName = filePath.split('/').pop() || filePath;
    appTitle.textContent = `SlowHands - ${fileName}`;
  }
  
  // Update status bar
  const statusRight = document.querySelector('#status-bar .right');
  if (statusRight) {
    // Find or create file path span
    let fileSpan = statusRight.querySelector('.current-file');
    if (!fileSpan) {
      fileSpan = document.createElement('span');
      fileSpan.className = 'current-file';
      statusRight.prepend(fileSpan);
    }
    fileSpan.textContent = filePath;
  }
}

// ============================================
// File Browser
// ============================================
interface FileItem {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  children?: FileItem[];
}

async function fetchWorkspaceFiles(): Promise<FileItem[]> {
  try {
    const response = await fetch(`${API_URL}/api/files`);
    if (!response.ok) throw new Error('Failed to fetch files');
    const data = await response.json();
    return data.files || [];
  } catch (e) {
    console.error('Error fetching workspace files:', e);
    return [];
  }
}

async function openFile(filePath: string): Promise<void> {
  try {
    const response = await fetch(`${API_URL}/api/files/${encodeURIComponent(filePath)}`);
    if (!response.ok) throw new Error('Failed to read file');
    const data = await response.json();
    updateEditorWithFile(filePath, data.content);
    addOutputLine(`📂 Opened: ${filePath}`);
  } catch (e) {
    console.error('Error opening file:', e);
    addOutputLine(`❌ Failed to open: ${filePath}`);
  }
}

function renderFileTree(files: FileItem[], container: HTMLElement, indent: number = 0): void {
  container.innerHTML = '';
  
  function createFileItem(file: FileItem, level: number): HTMLElement {
    const div = document.createElement('div');
    div.className = 'file-item';
    if (level > 0) div.classList.add('indent');
    div.style.paddingLeft = `${12 + level * 12}px`;
    
    const icon = file.type === 'directory' ? '📁' : '📄';
    div.textContent = `${icon} ${file.name}`;
    
    if (file.type === 'file') {
      div.style.cursor = 'pointer';
      div.addEventListener('click', () => openFile(file.path));
    }
    
    return div;
  }
  
  function addItems(items: FileItem[], level: number): void {
    for (const item of items) {
      container.appendChild(createFileItem(item, level));
      if (item.type === 'directory' && item.children) {
        addItems(item.children, level + 1);
      }
    }
  }
  
  if (files.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'file-item';
    empty.textContent = '(empty workspace)';
    empty.style.opacity = '0.5';
    container.appendChild(empty);
  } else {
    addItems(files, 0);
  }
}

async function refreshFileBrowser(): Promise<void> {
  const sidebarContent = document.querySelector('.sidebar-content');
  if (!sidebarContent) return;
  
  const files = await fetchWorkspaceFiles();
  renderFileTree(files, sidebarContent as HTMLElement);
}

// ============================================
// Backend Connection
// ============================================
const API_URL = 'http://127.0.0.1:8765';
const WS_URL = 'ws://127.0.0.1:8765/ws';

let websocket: WebSocket | null = null;
let isConnected = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const messageQueue: Array<{ type: string; content?: string; correlation_id?: string }> = [];
const MAX_QUEUE_SIZE = 50;

// Generate a simple correlation ID
function generateCorrelationId(): string {
  return `fe_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

// Ping latency tracking
let lastPingSentAt: number | null = null;
let lastPingLatencyMs: number | null = null;

function processMessageQueue() {
  if (!websocket || websocket.readyState !== WebSocket.OPEN) {
    return;
  }
  // #region debug log
  fetch('http://127.0.0.1:7244/ingest/578d1539-31a8-42d3-881d-710e16077329',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'frontend/src/main.ts:processMessageQueue',message:'queue_process_start',data:{queueSize:messageQueue.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'G'})}).catch(()=>{});
  // #endregion
  
  while (messageQueue.length > 0 && websocket.readyState === WebSocket.OPEN) {
    const message = messageQueue.shift();
    if (message) {
      try {
        websocket.send(JSON.stringify(message));
      } catch (e) {
        console.error('Error sending queued message:', e);
        // Re-queue if send failed
        messageQueue.unshift(message);
        break;
      }
    }
  }
  
  if (messageQueue.length > 0) {
    addOutputLine(`Processed queued messages. ${messageQueue.length} remaining.`);
  }
}

function connectWebSocket() {
  if (websocket?.readyState === WebSocket.OPEN) return;
  
  addOutputLine('Connecting to agent...');
  
  websocket = new WebSocket(WS_URL);
  
  websocket.onopen = () => {
    isConnected = true;
    reconnectAttempts = 0;
    addOutputLine('Connected to agent.');
    updateConnectionStatus(true);
    
    // #region debug log
    fetch('http://127.0.0.1:7244/ingest/578d1539-31a8-42d3-881d-710e16077329',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'frontend/src/main.ts:websocket.onopen',message:'ws_open',data:{readyState:websocket?.readyState},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'G'})}).catch(()=>{});
    // #endregion
    
    // Refresh file browser on connect
    refreshFileBrowser();
    
    // Process any queued messages
    if (messageQueue.length > 0) {
      addOutputLine(`Sending ${messageQueue.length} queued message(s)...`);
      processMessageQueue();
    }
  };
  
  websocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      // #region debug log
      fetch('http://127.0.0.1:7244/ingest/578d1539-31a8-42d3-881d-710e16077329',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'frontend/src/main.ts:websocket.onmessage',message:'raw_message',data:{rawLen:(event.data||'').length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'G'})}).catch(()=>{});
      // #endregion
      handleAgentMessage(data);
    } catch (e) {
      console.error('Failed to parse message:', e);
    }
  };
  
  websocket.onclose = () => {
    isConnected = false;
    updateConnectionStatus(false);
    
    // #region debug log
    fetch('http://127.0.0.1:7244/ingest/578d1539-31a8-42d3-881d-710e16077329',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'frontend/src/main.ts:websocket.onclose',message:'ws_close',data:{readyState:websocket?.readyState,reconnectAttempts},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'G'})}).catch(()=>{});
    // #endregion
    
    // Attempt reconnect with exponential backoff
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
      reconnectAttempts++;
      // Exponential backoff: 1s, 2s, 4s, 8s, 16s (capped at 5s)
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 5000);
      addOutputLine(`Reconnecting in ${delay/1000}s... (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
      setTimeout(connectWebSocket, delay);
    } else {
      addOutputLine('Connection failed. Start the server.');
      if (messageQueue.length > 0) {
        addOutputLine(`Warning: ${messageQueue.length} message(s) queued but connection failed.`);
      }
    }
  };
  
  websocket.onerror = (error) => {
    console.error('WebSocket error:', error);
    // #region debug log
    fetch('http://127.0.0.1:7244/ingest/578d1539-31a8-42d3-881d-710e16077329',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'frontend/src/main.ts:websocket.onerror',message:'ws_error',data:{readyState:websocket?.readyState},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'G'})}).catch(()=>{});
    // #endregion
  };
}

function handleAgentMessage(data: any) {
  const cid = data?.correlation_id || 'no-cid';
  // #region debug log
  fetch('http://127.0.0.1:7244/ingest/578d1539-31a8-42d3-881d-710e16077329',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'frontend/src/main.ts:handleAgentMessage',message:'ws_message_received',data:{type:data?.type,phase:data?.phase,contentLen:(data?.content||'').length,correlationId:cid},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
  // #endregion
  // Log correlation ID for debugging
  if (data?.correlation_id) {
    console.debug(`[${cid}] Received ${data.type} message`);
  }
  switch (data.type) {
    case 'step':
      // #region debug log
      fetch('http://127.0.0.1:7244/ingest/578d1539-31a8-42d3-881d-710e16077329',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.ts:handleAgentMessage:step',message:'step_received',data:{phase:data.phase,contentLen:(data.content||'').length,hasFileOp:!!data.file_op},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      
      // Handle file operations - update editor
      if (data.file_op) {
        const { action, path: filePath, content: fileContent } = data.file_op;
        if (filePath && fileContent !== undefined) {
          const actionEmoji = action === 'write' ? '📝' : '📖';
          addOutputLine(`${actionEmoji} ${action}: ${filePath}`);
          
          // Stream writes (so you can watch the code appear), instant for reads
          if (action === 'write') {
            // ~2 words per second = ~12 chars/sec (average word is 5-6 chars + space)
            const baseSpeed = 12; // chars per second
            // Slight speedup for very long files (over 1000 chars)
            const speedMultiplier = Math.min(2, 1 + fileContent.length / 2000);
            streamToEditor(filePath, fileContent, baseSpeed * speedMultiplier);
            // Refresh file browser after write
            setTimeout(() => refreshFileBrowser(), 500);
          } else {
            updateEditorWithFile(filePath, fileContent);
          }
        }
      }
      
      // Skip 'respond' phase since 'complete' will show the final response
      if (data.phase === 'respond') {
        break;
      }
      
      const phase = data.phase === 'act' ? '🔧' : '🧠';
      // Show more content (200 chars) for better context
      const stepContent = data.content.length > 200 
        ? data.content.substring(0, 200) + '...' 
        : data.content;
      addOutputLine(`${phase} ${stepContent}`);
      break;
    case 'complete':
      // #region debug log
      fetch('http://127.0.0.1:7244/ingest/578d1539-31a8-42d3-881d-710e16077329',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.ts:handleAgentMessage:complete',message:'complete_received',data:{contentLen:(data.content||'').length,contentPreview:(data.content||'').substring(0,80)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
      // #endregion
      // Show full response (up to 500 chars) for final answer
      const completeContent = data.content.length > 500 
        ? data.content.substring(0, 500) + '...' 
        : data.content;
      addOutputLine(`✅ ${completeContent}`);
      break;
    case 'stopped':
      addOutputLine(`⏹ Stopped`);
      break;
    case 'error':
      addOutputLine(`❌ Error: ${data.content}`);
      break;
    case 'pong':
      // Heartbeat response - calculate latency
      if (lastPingSentAt !== null) {
        lastPingLatencyMs = Date.now() - lastPingSentAt;
        lastPingSentAt = null;
        console.debug(`Ping latency: ${lastPingLatencyMs}ms`);
      }
      break;
    case 'file_content':
      // File content received from server
      if (data.path && data.content !== undefined) {
        updateEditorWithFile(data.path, data.content);
        addOutputLine(`📂 Opened: ${data.path}`);
      }
      break;
    default:
      console.log('Unknown message type:', data.type);
  }
}

function stopAgent() {
  if (!websocket || websocket.readyState !== WebSocket.OPEN) {
    addOutputLine('Not connected');
    return;
  }
  const correlationId = generateCorrelationId();
  websocket.send(JSON.stringify({ type: 'stop', correlation_id: correlationId }));
  console.debug(`[${correlationId}] Sending stop request`);
  addOutputLine('⏹ Stopping...');
}

function updateConnectionStatus(connected: boolean) {
  const statusIndicator = document.querySelector('#status-bar .left span:first-child');
  if (statusIndicator) {
    statusIndicator.textContent = connected ? '● Connected' : '○ Offline';
  }
}

function sendToAgent(message: string) {
  const correlationId = generateCorrelationId();
  // #region debug log
  fetch('http://127.0.0.1:7244/ingest/578d1539-31a8-42d3-881d-710e16077329',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'frontend/src/main.ts:sendToAgent',message:'send_invoked',data:{queueSize:messageQueue.length,wsState:websocket?.readyState ?? null,msgLen:message.length,correlationId},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
  // #endregion
  const messageObj = { type: 'chat', content: message, correlation_id: correlationId };
  
  if (!websocket || websocket.readyState !== WebSocket.OPEN) {
    // Queue the message
    if (messageQueue.length >= MAX_QUEUE_SIZE) {
      addOutputLine('Message queue full. Dropping oldest message.');
      messageQueue.shift();
    }
    messageQueue.push(messageObj);
    addOutputLine(`> ${message} (queued - ${messageQueue.length} in queue)`);
    
    // Try to connect if not already connecting
    if (!websocket || websocket.readyState === WebSocket.CONNECTING) {
      addOutputLine('Not connected. Connecting...');
      connectWebSocket();
    }
    return;
  }
  
  // Send immediately if connected
  try {
    websocket.send(JSON.stringify(messageObj));
    addOutputLine(`> ${message}`);
  } catch (e) {
    console.error('Error sending message:', e);
    // Queue if send failed
    if (messageQueue.length < MAX_QUEUE_SIZE) {
      messageQueue.push(messageObj);
      addOutputLine(`> ${message} (queued after send error)`);
    } else {
      addOutputLine('Error: Could not send message and queue is full.');
    }
  }
}

// ============================================
// Resizable Sidebar
// ============================================
const resizeHandle = document.getElementById('resize-handle') as HTMLElement;
const app = document.getElementById('app') as HTMLElement;
let isResizing = false;

resizeHandle.addEventListener('mousedown', (e) => {
  isResizing = true;
  resizeHandle.classList.add('dragging');
  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
  e.preventDefault();
});

document.addEventListener('mousemove', (e) => {
  if (!isResizing) return;
  
  const activityBarWidth = 50;
  const minWidth = 120;
  const maxWidth = 400;
  
  let newWidth = e.clientX - activityBarWidth;
  newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
  
  app.style.setProperty('--sidebar-width', `${newWidth}px`);
  editor.layout();
});

document.addEventListener('mouseup', () => {
  if (isResizing) {
    isResizing = false;
    resizeHandle.classList.remove('dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }
});

// ============================================
// Agent Panel
// ============================================
const agentInput = document.getElementById('agent-input') as HTMLInputElement;
const agentSend = document.getElementById('agent-send') as HTMLButtonElement;
const agentOutput = document.getElementById('agent-output') as HTMLElement;
const agentResizeHandle = document.getElementById('agent-resize-handle') as HTMLElement;
const agentPanel = document.getElementById('agent-panel') as HTMLElement;

// Store all output lines (scrollable history)
const outputLines: string[] = ['Initializing...'];

function updateOutput() {
  agentOutput.innerHTML = outputLines
    .map((line) => {
      const isThinking = line.includes('🧠') || line.includes('...');
      const isError = line.includes('❌') || line.includes('Error');
      const isSuccess = line.includes('✅');
      let className = 'output-line';
      if (isThinking) className += ' thinking';
      if (isError) className += ' error';
      if (isSuccess) className += ' success';
      return `<div class="${className}">${line}</div>`;
    })
    .join('');
  // Scroll to bottom
  agentOutput.scrollTop = agentOutput.scrollHeight;
}

function addOutputLine(text: string) {
  // #region debug log
  fetch('http://127.0.0.1:7244/ingest/578d1539-31a8-42d3-881d-710e16077329',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.ts:addOutputLine',message:'line_added',data:{textLen:text.length,textPreview:text.substring(0,60),totalLines:outputLines.length+1},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
  // #endregion
  outputLines.push(text);
  updateOutput();
}

function sendAgentMessage() {
  const message = agentInput.value.trim();
  if (!message) return;
  
  agentInput.value = '';
  sendToAgent(message);
}

const agentStop = document.getElementById('agent-stop') as HTMLButtonElement;

agentSend.addEventListener('click', sendAgentMessage);
agentStop?.addEventListener('click', stopAgent);
agentInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    sendAgentMessage();
  }
});

// ============================================
// Agent Panel Vertical Resize
// ============================================
let isResizingAgent = false;

if (agentResizeHandle) {
  agentResizeHandle.addEventListener('mousedown', (e) => {
    isResizingAgent = true;
    agentResizeHandle.classList.add('dragging');
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });
}

document.addEventListener('mousemove', (e) => {
  if (!isResizingAgent || !agentPanel) return;
  
  const rect = agentPanel.parentElement?.getBoundingClientRect();
  if (!rect) return;
  
  const minHeight = 80;
  const maxHeight = 300;
  const newHeight = rect.bottom - e.clientY;
  
  agentPanel.style.height = `${Math.max(minHeight, Math.min(maxHeight, newHeight))}px`;
});

document.addEventListener('mouseup', () => {
  if (isResizingAgent) {
    isResizingAgent = false;
    agentResizeHandle?.classList.remove('dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }
});

// ============================================
// Window Controls
// ============================================
document.getElementById('minimize-btn')?.addEventListener('click', () => {
  // @ts-ignore
  if (window.electronAPI?.minimize) window.electronAPI.minimize();
});

document.getElementById('maximize-btn')?.addEventListener('click', () => {
  // @ts-ignore
  if (window.electronAPI?.maximize) window.electronAPI.maximize();
});

document.getElementById('close-btn')?.addEventListener('click', () => {
  // @ts-ignore
  if (window.electronAPI?.close) window.electronAPI.close();
});

// ============================================
// Initialize
// ============================================
updateOutput();

// Connect to backend on startup
setTimeout(() => {
  connectWebSocket();
}, 500);

// Heartbeat to keep connection alive and measure latency
setInterval(() => {
  if (websocket?.readyState === WebSocket.OPEN) {
    lastPingSentAt = Date.now();
    websocket.send(JSON.stringify({ type: 'ping' }));
  }
}, 30000);

// ============================================
// Keyboard Shortcuts
// ============================================
document.addEventListener('keydown', (e) => {
  // Don't intercept if typing in input field
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
    return;
  }
  
  // Space - pause/resume streaming
  if (e.key === ' ' && isStreaming) {
    e.preventDefault();
    togglePause();
  }
  
  // Escape - skip streaming (show full content instantly)
  if (e.key === 'Escape' && isStreaming) {
    stopStreaming();
    addOutputLine('⏭ Skipped to end');
  }
});

// ============================================
// Toolbar Button Handlers
// ============================================
document.getElementById('pause-btn')?.addEventListener('click', () => {
  if (isStreaming) {
    togglePause();
  }
});

document.getElementById('skip-btn')?.addEventListener('click', () => {
  if (isStreaming) {
    stopStreaming();
    addOutputLine('⏭ Skipped to end');
  }
});
