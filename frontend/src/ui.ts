import { FileItem } from './types';
import Fuse from 'fuse.js';

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
    
    // Search properties
    private searchModal: HTMLElement | null = null;
    private searchInput: HTMLInputElement | null = null;
    private searchResults: HTMLElement | null = null;
    private fuse: Fuse<FileItem> | null = null;
    private flatFiles: FileItem[] = [];

    // Settings properties
    private settingsModal: HTMLElement | null = null;

    private outputLines: string[] = ['Initializing...'];

    constructor(
        private readonly onSendMessage: (msg: string) => void,
        private readonly onStopAgent: () => void,
        private readonly onOpenFile: (path: string) => Promise<void>,
        private readonly onOpenFolder: () => void,
        private readonly onNewFile: () => void,
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
        this.setupSearchModal();
        this.setupSettingsModal();
        this.setupActivityBar();
        this.updateOutput();
    }

    private setupSettingsModal() {
        this.settingsModal = document.createElement('div');
        this.settingsModal.className = 'search-modal settings-modal';
        this.settingsModal.innerHTML = `
            <div class="search-box settings-box" role="dialog" aria-labelledby="settings-title">
                <div class="settings-header">
                    <h2 id="settings-title">Settings</h2>
                    <button class="win-btn close" id="close-settings" aria-label="Close Settings">
                        <i class="codicon codicon-close"></i>
                    </button>
                </div>
                <div class="settings-content">
                    <div class="settings-group">
                        <h3>Appearance</h3>
                        <div class="setting-item">
                            <label for="theme-select">Theme</label>
                            <select id="theme-select" aria-label="Select Theme">
                                <option value="light">Light (Windows 11)</option>
                                <option value="dark" disabled>Dark (Coming Soon)</option>
                            </select>
                        </div>
                    </div>
                    <div class="settings-group">
                        <h3>Editor</h3>
                        <div class="setting-item">
                            <label for="font-size">Font Size</label>
                            <select id="font-size" aria-label="Select Font Size">
                                <option value="12">12px</option>
                                <option value="14" selected>14px</option>
                                <option value="16">16px</option>
                                <option value="18">18px</option>
                            </select>
                        </div>
                    </div>
                    <div class="settings-group">
                        <h3>About</h3>
                        <p style="font-size: 12px; color: var(--text-secondary);">
                            SlowHands v1.0.0<br>
                            Powered by Cursor & Roo
                        </p>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(this.settingsModal);

        // Close button
        this.settingsModal.querySelector('#close-settings')?.addEventListener('click', () => {
            this.hideSettings();
        });

        // Click outside
        this.settingsModal.addEventListener('click', (e) => {
            if (e.target === this.settingsModal) this.hideSettings();
        });
    }

    private showSettings() {
        if (this.settingsModal) {
            this.settingsModal.classList.add('visible');
        }
    }

    private hideSettings() {
        if (this.settingsModal) {
            this.settingsModal.classList.remove('visible');
        }
    }

    private setupActivityBar() {
        const activityBar = document.getElementById('activity-bar');
        if (activityBar) {
            // Add settings icon at the bottom
            const spacer = document.createElement('div');
            spacer.style.flex = '1';
            activityBar.appendChild(spacer);

            const settingsBtn = document.createElement('div');
            settingsBtn.className = 'icon';
            settingsBtn.title = 'Settings';
            settingsBtn.setAttribute('role', 'button');
            settingsBtn.setAttribute('aria-label', 'Settings');
            settingsBtn.innerHTML = '<i class="codicon codicon-settings-gear"></i>';
            settingsBtn.addEventListener('click', () => this.showSettings());
            activityBar.appendChild(settingsBtn);
        }
    }

    private setupSearchModal() {
        // Create modal
        this.searchModal = document.createElement('div');
        this.searchModal.className = 'search-modal';
        this.searchModal.setAttribute('role', 'dialog');
        this.searchModal.setAttribute('aria-modal', 'true');
        this.searchModal.setAttribute('aria-label', 'File Search');
        
        this.searchModal.innerHTML = `
            <div class="search-box">
                <input type="text" placeholder="Search files (Ctrl+P)..." id="file-search-input" autocomplete="off" aria-label="Search files" role="combobox" aria-autocomplete="list" aria-controls="file-search-results" aria-expanded="true">
                <div class="search-results" id="file-search-results" role="listbox"></div>
            </div>
        `;
        document.body.appendChild(this.searchModal);
        
        this.searchInput = this.searchModal.querySelector('#file-search-input');
        this.searchResults = this.searchModal.querySelector('#file-search-results');
        
        // Listeners
        this.searchInput?.addEventListener('input', () => this.handleSearch());
        this.searchInput?.addEventListener('keydown', (e) => this.handleSearchKeydown(e));
        
        // Click outside to close
        this.searchModal.addEventListener('click', (e) => {
            if (e.target === this.searchModal) this.hideSearch();
        });
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

    private flattenFiles(files: FileItem[]): FileItem[] {
        let result: FileItem[] = [];
        for (const file of files) {
            if (file.type === 'file') {
                result.push(file);
            }
            if (file.children) {
                result = result.concat(this.flattenFiles(file.children));
            }
        }
        return result;
    }

    private showSearch() {
        if (this.searchModal && this.searchInput) {
            this.searchModal.classList.add('visible');
            this.searchInput.value = '';
            this.searchInput.focus();
            this.handleSearch(); // Clear results
        }
    }

    private hideSearch() {
        if (this.searchModal) {
            this.searchModal.classList.remove('visible');
        }
    }

    private handleSearch() {
        if (!this.searchInput || !this.searchResults || !this.fuse) return;
        
        const query = this.searchInput.value.trim();
        this.searchResults.innerHTML = '';
        
        let results: FileItem[] = [];
        if (query.length === 0) {
            // Show recent or first few files if empty? Or just empty
            // Let's show nothing if empty
            return;
        } else {
            results = this.fuse.search(query).map(result => result.item);
        }
        
        results.slice(0, 20).forEach((file, index) => {
            const el = document.createElement('div');
            el.className = 'search-result-item';
            el.setAttribute('role', 'option');
            el.setAttribute('aria-selected', index === 0 ? 'true' : 'false');
            if (index === 0) el.classList.add('selected');
            
            el.innerHTML = `
                <div class="search-result-name">${this.escapeHtml(file.name)}</div>
                <div class="search-result-path">${this.escapeHtml(file.path)}</div>
            `;
            
            el.addEventListener('click', () => {
                this.onOpenFile(file.path);
                this.hideSearch();
            });
            
            el.addEventListener('mouseenter', () => {
                this.searchResults?.querySelectorAll('.search-result-item.selected').forEach(e => {
                    e.classList.remove('selected');
                    e.setAttribute('aria-selected', 'false');
                });
                el.classList.add('selected');
                el.setAttribute('aria-selected', 'true');
            });
            
            this.searchResults!.appendChild(el);
        });
    }

    private handleSearchKeydown(e: KeyboardEvent) {
        if (e.key === 'Escape') {
            this.hideSearch();
            e.preventDefault();
        } else if (e.key === 'Enter') {
            const selected = this.searchResults?.querySelector('.search-result-item.selected') as HTMLElement;
            if (selected) {
                selected.click();
            }
            e.preventDefault();
        } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            const items = Array.from(this.searchResults?.querySelectorAll('.search-result-item') || []);
            if (items.length === 0) return;
            
            const currentIndex = items.findIndex(el => el.classList.contains('selected'));
            let newIndex = 0;
            
            if (currentIndex !== -1) {
                if (e.key === 'ArrowDown') {
                    newIndex = (currentIndex + 1) % items.length;
                } else {
                    newIndex = (currentIndex - 1 + items.length) % items.length;
                }
            }
            
            items.forEach(el => {
                el.classList.remove('selected');
                el.setAttribute('aria-selected', 'false');
            });
            items[newIndex].classList.add('selected');
            items[newIndex].setAttribute('aria-selected', 'true');
            items[newIndex].scrollIntoView({ block: 'nearest' });
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

        // Setup dropdown menus
        const menuContainers = document.querySelectorAll('.menu-container');
        menuContainers.forEach(container => {
            const trigger = container.querySelector('.menu-trigger');
            const menu = container.querySelector('.dropdown-menu');

            if (trigger && menu) {
                trigger.addEventListener('click', (e) => {
                    e.stopPropagation();
                    
                    // Close other menus
                    document.querySelectorAll('.menu-container.open').forEach(el => {
                        if (el !== container) el.classList.remove('open');
                    });
                    
                    container.classList.toggle('open');
                });

                // Hover to switch menus when one is already open
                trigger.addEventListener('mouseenter', () => {
                    const anyOpen = document.querySelector('.menu-container.open');
                    if (anyOpen && anyOpen !== container) {
                        anyOpen.classList.remove('open');
                        container.classList.add('open');
                    }
                });
            }
        });

        // Close dropdowns when clicking outside
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
            
            // New File
            if (text.includes('New File')) {
                item.addEventListener('click', () => {
                    this.onNewFile();
                });
            }

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
            if (text.includes('Save') && !text.includes('Save As')) {
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
            
            // Save As
            if (text.includes('Save As')) {
                item.addEventListener('click', async () => {
                    try {
                        const { content } = this.onGetCurrentFile();
                        // Always show save dialog for Save As
                        // @ts-ignore
                        const filePath = await window.electronAPI?.saveFileDialog();
                        if (filePath) {
                            await this.onSaveFile(filePath, content);
                            this.addOutputLine(`[Save As] ${filePath}`);
                        }
                    } catch (error) {
                        console.error('Failed to save file:', error);
                        this.addOutputLine(`[Error] Failed to save file`);
                    }
                });
            }
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
            // Ctrl+N: New File
            if (e.ctrlKey && e.key === 'n') {
                e.preventDefault();
                this.onNewFile();
            }

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
            
            // Ctrl+P: Quick Open (File Search)
            if (e.ctrlKey && e.key === 'p') {
                e.preventDefault();
                this.showSearch();
            }
            
            // Ctrl+S: Save
            if (e.ctrlKey && e.key === 's' && !e.shiftKey) {
                e.preventDefault();
                const saveItem = Array.from(document.querySelectorAll('.menu-item'))
                    .find(item => item.textContent?.includes('Save') && !item.textContent?.includes('Save As'));
                if (saveItem) {
                    (saveItem as HTMLElement).click();
                }
            }
            
            // Ctrl+Shift+S: Save As
            if (e.ctrlKey && e.shiftKey && e.key === 'S') {
                e.preventDefault();
                const saveItem = Array.from(document.querySelectorAll('.menu-item'))
                    .find(item => item.textContent?.includes('Save As'));
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

    private getFileIcon(file: FileItem): string {
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
    }

    public renderFileTree(files: FileItem[]) {
        // Update search index
        this.flatFiles = this.flattenFiles(files);
        this.fuse = new Fuse(this.flatFiles, {
            keys: ['name', 'path'],
            threshold: 0.4,
        });

        this.sidebarContent.innerHTML = '';
        
        const createTreeNode = (file: FileItem, level: number): HTMLElement => {
            const container = document.createElement('div');
            container.className = 'tree-node';
            
            const content = document.createElement('div');
            content.className = 'file-item';
            content.setAttribute('role', 'treeitem');
            content.setAttribute('aria-label', file.name);
            content.setAttribute('aria-level', String(level + 1));
            
            // Calculate padding: base 12px + level * 12px
            content.style.paddingLeft = `${12 + level * 12}px`;
            
            let innerHTML = '';
            
            if (file.type === 'directory') {
                innerHTML = `<i class="codicon codicon-chevron-right caret"></i> ${this.getFileIcon(file)} <span class="file-name">${this.escapeHtml(file.name)}</span>`;
            } else {
                // Spacer for alignment (caret width)
                innerHTML = `<span class="caret-spacer"></span> ${this.getFileIcon(file)} <span class="file-name">${this.escapeHtml(file.name)}</span>`;
            }
            content.innerHTML = innerHTML;
            
            container.appendChild(content);
            
            if (file.type === 'directory') {
                const childrenContainer = document.createElement('div');
                childrenContainer.className = 'tree-children';
                childrenContainer.style.display = 'none'; // Default collapsed
                
                if (file.children) {
                    // Sort: directories first, then files
                    const sortedChildren = [...file.children].sort((a, b) => {
                        if (a.type === b.type) return a.name.localeCompare(b.name);
                        return a.type === 'directory' ? -1 : 1;
                    });
                    
                    sortedChildren.forEach(child => {
                        childrenContainer.appendChild(createTreeNode(child, level + 1));
                    });
                }
                container.appendChild(childrenContainer);
                
                // Toggle handler
                content.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const isCollapsed = childrenContainer.style.display === 'none';
                    childrenContainer.style.display = isCollapsed ? 'block' : 'none';
                    
                    const caret = content.querySelector('.caret');
                    if (caret) {
                        if (isCollapsed) {
                            caret.classList.replace('codicon-chevron-right', 'codicon-chevron-down');
                        } else {
                            caret.classList.replace('codicon-chevron-down', 'codicon-chevron-right');
                        }
                    }
                    
                    const folderIcon = content.querySelector('.codicon-folder, .codicon-folder-opened');
                    if (folderIcon) {
                         if (isCollapsed) {
                            folderIcon.classList.replace('codicon-folder', 'codicon-folder-opened');
                         } else {
                            folderIcon.classList.replace('codicon-folder-opened', 'codicon-folder');
                         }
                    }
                });
            } else {
                // File handlers
                content.style.cursor = 'pointer';
                content.tabIndex = 0;
                
                content.addEventListener('click', () => {
                    document.querySelectorAll('.file-item.selected').forEach(el => {
                        el.classList.remove('selected');
                        el.setAttribute('aria-selected', 'false');
                    });
                    content.classList.add('selected');
                    content.setAttribute('aria-selected', 'true');
                });

                content.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        this.onOpenFile(file.path);
                    }
                });
                
                content.addEventListener('dblclick', () => this.onOpenFile(file.path));
                
                content.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    document.querySelectorAll('.file-item.selected').forEach(el => {
                        el.classList.remove('selected');
                        el.setAttribute('aria-selected', 'false');
                    });
                    content.classList.add('selected');
                    content.setAttribute('aria-selected', 'true');
                    this.showContextMenu(e.clientX, e.clientY, file.path);
                });
            }
            
            return container;
        };
        
        if (files.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'file-item';
            empty.innerHTML = '<i class="codicon codicon-info"></i> (empty workspace)';
            empty.style.opacity = '0.5';
            empty.style.paddingLeft = '12px';
            this.sidebarContent.appendChild(empty);
        } else {
             // Sort root files
            const sortedFiles = [...files].sort((a, b) => {
                if (a.type === b.type) return a.name.localeCompare(b.name);
                return a.type === 'directory' ? -1 : 1;
            });
            sortedFiles.forEach(f => {
                this.sidebarContent.appendChild(createTreeNode(f, 0));
            });
        }
    }
}
