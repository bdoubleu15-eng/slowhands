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

    private outputLines: string[] = ['Initializing...'];
    private isThinking: boolean = false;

    constructor(
        private readonly onSendMessage: (msg: string) => void,
        private readonly onStopAgent: () => void,
        private readonly onOpenFile: (path: string) => void,
        private readonly onTogglePause: () => void,
        private readonly onSkipStreaming: () => void
    ) {
        this.agentOutput = document.getElementById('agent-output') as HTMLElement;
        this.agentInput = document.getElementById('agent-input') as HTMLInputElement;
        this.sidebarContent = document.querySelector('.sidebar-content') as HTMLElement;
        this.connectionStatus = document.getElementById('connection-status');
        this.appTitle = document.querySelector('.app-title');
        this.pauseBtn = document.getElementById('pause-btn');
        this.thinkingIndicator = document.getElementById('thinking-indicator');

        this.setupEventListeners();
        this.updateOutput();
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
                div.addEventListener('click', () => this.onOpenFile(file.path));
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
