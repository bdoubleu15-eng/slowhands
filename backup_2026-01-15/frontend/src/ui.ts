import { FileItem } from './types';

export class UIManager {
    private agentOutput: HTMLElement;
    private agentInput: HTMLInputElement;
    private sidebarContent: HTMLElement;
    private statusIndicator: HTMLElement | null;
    private currentFileSpan: HTMLElement | null = null;
    private appTitle: HTMLElement | null;
    private pauseBtn: HTMLElement | null;

    private outputLines: string[] = ['Initializing...'];

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
        this.statusIndicator = document.querySelector('#status-bar .left span:first-child');
        this.appTitle = document.querySelector('.app-title');
        this.pauseBtn = document.getElementById('pause-btn');

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
    }

    private handleSendMessage() {
        const message = this.agentInput.value.trim();
        if (message) {
            this.agentInput.value = '';
            this.onSendMessage(message);
        }
    }

    public updateOutput() {
        this.agentOutput.innerHTML = this.outputLines
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
        this.agentOutput.scrollTop = this.agentOutput.scrollHeight;
    }

    public addOutputLine(text: string) {
        this.outputLines.push(text);
        this.updateOutput();
    }

    public updateConnectionStatus(connected: boolean) {
        if (this.statusIndicator) {
            this.statusIndicator.textContent = connected ? '● Connected' : '○ Offline';
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
                this.currentFileSpan.className = 'current-file';
                statusRight.prepend(this.currentFileSpan);
            }
            this.currentFileSpan.textContent = filePath;
        }
    }

    public updatePauseButton(isPaused: boolean, isStreaming: boolean) {
        if (this.pauseBtn) {
            this.pauseBtn.textContent = isPaused ? '▶' : '⏸';
            this.pauseBtn.title = isPaused ? 'Resume streaming (Space)' : 'Pause streaming (Space)';
            this.pauseBtn.style.opacity = isStreaming ? '1' : '0.5';
        }
    }

    public renderFileTree(files: FileItem[]) {
        this.sidebarContent.innerHTML = '';
        
        const createFileItem = (file: FileItem, level: number): HTMLElement => {
            const div = document.createElement('div');
            div.className = 'file-item';
            if (level > 0) div.classList.add('indent');
            div.style.paddingLeft = `${12 + level * 12}px`;
            
            const icon = file.type === 'directory' ? '📁' : '📄';
            div.textContent = `${icon} ${file.name}`;
            
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
            empty.textContent = '(empty workspace)';
            empty.style.opacity = '0.5';
            this.sidebarContent.appendChild(empty);
        } else {
            addItems(files, 0);
        }
    }
}
