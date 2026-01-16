import { FileItem } from './types';

export class UIManager {
    private agentOutput: HTMLElement;
    private agentInput: HTMLInputElement;
    private sidebarContent: HTMLElement;
    private connectionStatus: HTMLElement | null;
    private currentFileSpan: HTMLElement | null = null;
    private appTitle: HTMLElement | null;
    private pauseBtn: HTMLElement | null;
    private thinkingIndicator: HTMLElement | null;
    private contextMenu: HTMLElement | null = null;
    private selectedFilePath: string | null = null;
    private recordingIndicator: HTMLElement | null = null;

    private outputLines: string[] = ['Initializing...'];
    private isThinking: boolean = false;
    private isRecording: boolean = false;
    private isTranscribing: boolean = false;

    constructor(
        private readonly onSendMessage: (msg: string) => void,
        private readonly onStopAgent: () => void,
        private readonly onOpenFile: (path: string) => void,
        private readonly onOpenFolder: () => void,
        private readonly onTogglePause: () => void,
        private readonly onSkipStreaming: () => void,
        private readonly onSaveFile: (path: string, content: string) => Promise<void>,
        private readonly onGetCurrentFile: () => { path: string | null; content: string }
    ) {
        this.agentOutput = document.getElementById('agent-output') as HTMLElement;
        this.agentInput = document.getElementById('agent-input') as HTMLInputElement;
        this.sidebarContent = document.querySelector('.sidebar-content') as HTMLElement;
        this.connectionStatus = document.getElementById('connection-status');
        this.appTitle = document.querySelector('.app-title');
        this.pauseBtn = document.getElementById('pause-btn');
        this.thinkingIndicator = document.getElementById('thinking-indicator');

        this.setupEventListeners();
        this.setupContextMenu();
        this.setupRecordingIndicator();
        this.updateOutput();
    }

    private setupContextMenu() {
        // Create context menu element
        this.contextMenu = document.createElement('div');
        this.contextMenu.className = 'context-menu';
        this.contextMenu.innerHTML = `
            <div class="context-menu-item" data-action="open">
                <i class="codicon codicon-go-to-file"></i> Open
            </div>
        `;
        document.body.appendChild(this.contextMenu);

        // Handle context menu item clicks
        this.contextMenu.addEventListener('click', (e) => {
            const target = e.target as HTMLElement;
            const menuItem = target.closest('.context-menu-item') as HTMLElement;
            if (menuItem && this.selectedFilePath) {
                const action = menuItem.dataset.action;
                if (action === 'open') {
                    this.onOpenFile(this.selectedFilePath);
                }
            }
            this.hideContextMenu();
        });

        // Hide context menu on click outside
        document.addEventListener('click', (e) => {
            if (this.contextMenu && !this.contextMenu.contains(e.target as Node)) {
                this.hideContextMenu();
            }
        });

        // Hide context menu on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideContextMenu();
            }
        });
    }

    private showContextMenu(x: number, y: number, filePath: string) {
        if (!this.contextMenu) return;
        
        this.selectedFilePath = filePath;
        this.contextMenu.style.left = `${x}px`;
        this.contextMenu.style.top = `${y}px`;
        this.contextMenu.classList.add('visible');
    }

    private hideContextMenu() {
        if (this.contextMenu) {
            this.contextMenu.classList.remove('visible');
            this.selectedFilePath = null;
        }
    }

    private setupEventListeners() {
        const agentSend = document.getElementById('agent-send');
        const agentStop = document.getElementById('agent-stop');

        agentSend?.addEventListener('click', () => this.handleSendMessage());
        agentStop?.addEventListener('click', () => this.onStopAgent());
        
        this.agentInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.handleSendMessage();
        });

        this.pauseBtn?.addEventListener('click', () => this.onTogglePause());
        document.getElementById('skip-btn')?.addEventListener('click', () => this.onSkipStreaming());

        // Window controls
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

        // Setup dropdown menus - close when clicking outside
        document.addEventListener('click', (e) => {
            const target = e.target as HTMLElement;
            if (!target.closest('.menu-container')) {
                document.querySelectorAll('.menu-container.open').forEach(el => {
                    el.classList.remove('open');
                });
            }
        });

        // Setup file menu handlers
        this.setupFileMenuHandlers();
        
        // Setup keyboard shortcuts
        this.setupKeyboardShortcuts();
    }

    private setupFileMenuHandlers() {
        // Get all menu items
        const menuItems = document.querySelectorAll('.menu-item');
        
        menuItems.forEach(item => {
            const text = item.textContent || '';
            
            // Open Folder
            if (text.includes('Open Folder')) {
                item.addEventListener('click', () => {
                    this.onOpenFolder();
                });
            }
            
            // Open File
            if (text.includes('Open File') && !text.includes('Folder')) {
                item.addEventListener('click', async () => {
                    try {
                        // @ts-ignore
                        const filePath = await window.electronAPI?.openFileDialog();
                        if (filePath) {
                            this.onOpenFile(filePath);
                        }
                    } catch (error) {
                        console.error('Failed to open file dialog:', error);
                        this.addOutputLine(`[Error] Failed to open file dialog`);
                    }
                });
            }
            
            // Save
            if (text.includes('Save') && !text.includes('Save All')) {
                item.addEventListener('click', async () => {
                    try {
                        const { path: currentPath, content } = this.onGetCurrentFile();
                        if (!currentPath) {
                            // No file open, show save dialog
                            // @ts-ignore
                            const filePath = await window.electronAPI?.saveFileDialog();
                            if (filePath) {
                                await this.onSaveFile(filePath, content);
                                this.addOutputLine(`[Save] ${filePath}`);
                            }
                        } else {
                            // Save to current file
                            await this.onSaveFile(currentPath, content);
                            this.addOutputLine(`[Save] ${currentPath}`);
                        }
                    } catch (error) {
                        console.error('Failed to save file:', error);
                        this.addOutputLine(`[Error] Failed to save file`);
                    }
                });
            }
            
            // Save As (handled via Save when no file is open)
            // Close File
            if (text.includes('Close File')) {
                item.addEventListener('click', () => {
                    // TODO: Implement close file functionality
                    this.addOutputLine('[Info] Close file not yet implemented');
                });
            }
        });
    }

    private setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl+Shift+O: Open Folder
            if (e.ctrlKey && e.shiftKey && e.key === 'O') {
                e.preventDefault();
                this.onOpenFolder();
            }
            
            // Ctrl+O: Open File
            if (e.ctrlKey && !e.shiftKey && e.key === 'o') {
                e.preventDefault();
                const openItem = Array.from(document.querySelectorAll('.menu-item'))
                    .find(item => item.textContent?.includes('Open File') && !item.textContent?.includes('Folder'));
                if (openItem) {
                    (openItem as HTMLElement).click();
                }
            }
            
            // Ctrl+S: Save
            if (e.ctrlKey && e.key === 's' && !e.shiftKey) {
                e.preventDefault();
                const saveItem = Array.from(document.querySelectorAll('.menu-item'))
                    .find(item => item.textContent?.includes('Save') && !item.textContent?.includes('Save All'));
                if (saveItem) {
                    (saveItem as HTMLElement).click();
                }
            }
            
            // Ctrl+Shift+S: Save As (same as Save when no file open)
            if (e.ctrlKey && e.shiftKey && e.key === 'S') {
                e.preventDefault();
                const saveItem = Array.from(document.querySelectorAll('.menu-item'))
                    .find(item => item.textContent?.includes('Save') && !item.textContent?.includes('Save All'));
                if (saveItem) {
                    (saveItem as HTMLElement).click();
                }
            }
        });
    }

    private handleSendMessage() {
        const message = this.agentInput.value.trim();
        if (message) {
            this.agentInput.value = '';
            this.onSendMessage(message);
            // Show thinking indicator immediately
            this.setThinking(true);
        }
    }

    public setThinking(thinking: boolean) {
        this.isThinking = thinking;
        if (this.thinkingIndicator) {
            if (thinking) {
                this.thinkingIndicator.classList.add('visible');
            } else {
                this.thinkingIndicator.classList.remove('visible');
            }
        }
    }

    private setupRecordingIndicator() {
        // Create recording indicator element
        this.recordingIndicator = document.createElement('div');
        this.recordingIndicator.className = 'recording-indicator';
        this.recordingIndicator.innerHTML = `
            <div class="recording-dot"></div>
            <span class="recording-text">Recording</span>
        `;

        // Add to the input area
        const inputArea = document.querySelector('.agent-input-container');
        if (inputArea) {
            inputArea.appendChild(this.recordingIndicator);
        }
    }

    public setRecording(recording: boolean) {
        this.isRecording = recording;
        if (this.recordingIndicator) {
            if (recording) {
                this.recordingIndicator.classList.add('visible');
                this.recordingIndicator.querySelector('.recording-text')!.textContent = 'Recording';
            } else {
                this.recordingIndicator.classList.remove('visible');
            }
        }
    }

    public setTranscribing(transcribing: boolean) {
        this.isTranscribing = transcribing;
        if (this.recordingIndicator) {
            if (transcribing) {
                this.recordingIndicator.classList.add('visible');
                this.recordingIndicator.querySelector('.recording-text')!.textContent = 'Transcribing...';
                this.recordingIndicator.querySelector('.recording-dot')!.classList.add('processing');
            } else if (!this.isRecording) {
                this.recordingIndicator.classList.remove('visible');
                this.recordingIndicator.querySelector('.recording-dot')!.classList.remove('processing');
            }
        }
    }

    public insertIntoInput(text: string) {
        // Insert transcribed text at cursor position or append to existing
        const currentValue = this.agentInput.value;
        const cursorPos = this.agentInput.selectionStart || currentValue.length;

        const before = currentValue.slice(0, cursorPos);
        const after = currentValue.slice(cursorPos);

        // Add space if needed
        const needsSpace = before.length > 0 && !before.endsWith(' ') && !text.startsWith(' ');
        const newValue = before + (needsSpace ? ' ' : '') + text + after;

        this.agentInput.value = newValue;
        this.agentInput.focus();

        // Set cursor after inserted text
        const newCursorPos = cursorPos + (needsSpace ? 1 : 0) + text.length;
        this.agentInput.setSelectionRange(newCursorPos, newCursorPos);
    }

    public updateOutput() {
        this.agentOutput.innerHTML = this.outputLines
            .map((line) => {
                const isThinking = line.includes('Thinking') || line.includes('...');
                const isError = line.includes('Error') || line.includes('Failed');
                const isSuccess = line.includes('Complete') || line.includes('Done');
                let className = 'output-line';
                if (isThinking) className += ' thinking';
                if (isError) className += ' error';
                if (isSuccess) className += ' success';
                return `<div class="${className}">${this.escapeHtml(line)}</div>`;
            })
            .join('');
        this.agentOutput.scrollTop = this.agentOutput.scrollHeight;
    }

    private escapeHtml(text: string): string {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    public addOutputLine(text: string) {
        // Strip emoji and replace with descriptive text for cleaner look
        const cleanText = text
            .replace(/🧠/g, '[Think]')
            .replace(/🔧/g, '[Act]')
            .replace(/✅/g, '[Done]')
            .replace(/❌/g, '[Error]')
            .replace(/📝/g, '[Write]')
            .replace(/📖/g, '[Read]')
            .replace(/📂/g, '[Open]')
            .replace(/⏸/g, '[Pause]')
            .replace(/▶/g, '[Resume]')
            .replace(/⏭/g, '[Skip]')
            .replace(/⏹/g, '[Stop]');
        
        this.outputLines.push(cleanText);
        this.updateOutput();

        // Hide thinking indicator when we get a response
        if (text.includes('Complete') || text.includes('Error') || text.includes('Stopped')) {
            this.setThinking(false);
        }
    }

    public updateConnectionStatus(connected: boolean) {
        if (this.connectionStatus) {
            if (connected) {
                this.connectionStatus.innerHTML = '<i class="codicon codicon-circle-filled"></i> Connected';
            } else {
                this.connectionStatus.innerHTML = '<i class="codicon codicon-circle-outline"></i> Offline';
            }
        }
    }

    public updateFileNameDisplay(filePath: string) {
        if (this.appTitle) {
            const fileName = filePath.split('/').pop() || filePath;
            this.appTitle.textContent = `SlowHands - ${fileName}`;
        }
        
        const statusRight = document.querySelector('#status-bar .right');
        if (statusRight) {
            if (!this.currentFileSpan) {
                this.currentFileSpan = document.createElement('span');
                this.currentFileSpan.className = 'status-item current-file';
                statusRight.prepend(this.currentFileSpan);
            }
            this.currentFileSpan.textContent = filePath;
        }
    }

    public updatePauseButton(isPaused: boolean, isStreaming: boolean) {
        if (this.pauseBtn) {
            this.pauseBtn.innerHTML = isPaused 
                ? '<i class="codicon codicon-debug-start"></i>' 
                : '<i class="codicon codicon-debug-pause"></i>';
            this.pauseBtn.title = isPaused ? 'Resume streaming (Space)' : 'Pause streaming (Space)';
            this.pauseBtn.style.opacity = isStreaming ? '1' : '0.5';
        }
    }

    public renderFileTree(files: FileItem[]) {
        this.sidebarContent.innerHTML = '';
        
        const getFileIcon = (file: FileItem): string => {
            if (file.type === 'directory') {
                return '<i class="codicon codicon-folder"></i>';
            }
            
            const ext = file.name.split('.').pop()?.toLowerCase();
            switch (ext) {
                case 'py':
                    return '<i class="codicon codicon-file-code" style="color: #3572a5"></i>';
                case 'ts':
                case 'tsx':
                    return '<i class="codicon codicon-file-code" style="color: #3178c6"></i>';
                case 'js':
                case 'jsx':
                    return '<i class="codicon codicon-file-code" style="color: #f1e05a"></i>';
                case 'json':
                    return '<i class="codicon codicon-json" style="color: #cbcb41"></i>';
                case 'md':
                    return '<i class="codicon codicon-markdown" style="color: #083fa1"></i>';
                case 'html':
                    return '<i class="codicon codicon-file-code" style="color: #e34c26"></i>';
                case 'css':
                    return '<i class="codicon codicon-file-code" style="color: #563d7c"></i>';
                case 'yml':
                case 'yaml':
                    return '<i class="codicon codicon-file-code" style="color: #cb171e"></i>';
                case 'sh':
                case 'bash':
                    return '<i class="codicon codicon-terminal" style="color: #89e051"></i>';
                case 'txt':
                    return '<i class="codicon codicon-file"></i>';
                default:
                    return '<i class="codicon codicon-file"></i>';
            }
        };
        
        const createFileItem = (file: FileItem, level: number): HTMLElement => {
            const div = document.createElement('div');
            div.className = 'file-item';
            if (level > 0) div.classList.add('indent');
            div.style.paddingLeft = `${12 + level * 12}px`;
            
            div.innerHTML = `${getFileIcon(file)} ${this.escapeHtml(file.name)}`;
            
            if (file.type === 'file') {
                div.style.cursor = 'pointer';
                
                // Single click just highlights the file
                div.addEventListener('click', () => {
                    // Remove selected class from all items
                    document.querySelectorAll('.file-item.selected').forEach(el => {
                        el.classList.remove('selected');
                    });
                    div.classList.add('selected');
                });
                
                // Double click opens the file
                div.addEventListener('dblclick', () => this.onOpenFile(file.path));
                
                // Right click shows context menu
                div.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    // Highlight the file
                    document.querySelectorAll('.file-item.selected').forEach(el => {
                        el.classList.remove('selected');
                    });
                    div.classList.add('selected');
                    this.showContextMenu(e.clientX, e.clientY, file.path);
                });
            }
            
            return div;
        };
        
        const addItems = (items: FileItem[], level: number) => {
            for (const item of items) {
                this.sidebarContent.appendChild(createFileItem(item, level));
                if (item.type === 'directory' && item.children) {
                    addItems(item.children, level + 1);
                }
            }
        };
        
        if (files.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'file-item';
            empty.innerHTML = '<i class="codicon codicon-info"></i> (empty workspace)';
            empty.style.opacity = '0.5';
            this.sidebarContent.appendChild(empty);
        } else {
            addItems(files, 0);
        }
    }
}
