import type * as Monaco from 'monaco-editor'
import { EditorTab } from './types'

interface TabModel {
    model: Monaco.editor.ITextModel;
    viewState: Monaco.editor.ICodeEditorViewState | null;
}

export class EditorManager {
    private editor: Monaco.editor.IStandaloneCodeEditor | null = null;
    private monaco: typeof Monaco | null = null;
    private tabs: EditorTab[] = [];
    private tabModels: Map<string, TabModel> = new Map();
    private activeTabId: string | null = null;
    private tabBarElement: HTMLElement | null = null;
    
    private initPromise: Promise<void> | null = null;
    
    public readonly MAX_TABS = 5;
    
    // Streaming state
    private isStreaming = false;
    private isPaused = false;
    private streamingAbortController: AbortController | null = null;
    private streamingTabId: string | null = null;
    private pendingStreamContent: string | null = null;
    private currentStreamingContent: string | null = null;

    // Callbacks
    public onFileChanged: (filePath: string) => void = () => {};
    public onTabsChanged: () => void = () => {};

    constructor(private container: HTMLElement) {
        this.showPlaceholder();
    }

    private showPlaceholder() {
        this.container.innerHTML = `
            <div class="editor-placeholder">
                <div class="hands-svg">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/>
                    </svg>
                </div>
                <div style="font-size: 14px; font-weight: 500; margin-bottom: 8px;">SlowHands Editor</div>
                <div style="font-size: 12px; opacity: 0.6;">Open a file to start coding</div>
            </div>
        `;
    }

    private ensureInitialized(): Promise<void> {
        if (!this.initPromise) {
            this.initPromise = this.init();
        }
        return this.initPromise;
    }

    private async init() {
        // Show loading indicator
        this.container.innerHTML = `
            <div class="editor-placeholder">
                <div class="spinner" style="margin-bottom: 12px;"></div>
                <div>Loading Editor...</div>
            </div>
        `;

        // Load Monaco and workers in parallel
        // Using dynamic imports for code splitting
        const [
            monaco,
            editorWorker,
            jsonWorker,
            cssWorker,
            htmlWorker,
            tsWorker
        ] = await Promise.all([
            import('monaco-editor'),
            import('monaco-editor/esm/vs/editor/editor.worker?worker'),
            import('monaco-editor/esm/vs/language/json/json.worker?worker'),
            import('monaco-editor/esm/vs/language/css/css.worker?worker'),
            import('monaco-editor/esm/vs/language/html/html.worker?worker'),
            import('monaco-editor/esm/vs/language/typescript/ts.worker?worker')
        ]);

        this.monaco = monaco;

        // Configure Monaco Environment
        self.MonacoEnvironment = {
            getWorker(_, label) {
                if (label === 'json') {
                    return new jsonWorker.default()
                }
                if (label === 'css' || label === 'scss' || label === 'less') {
                    return new cssWorker.default()
                }
                if (label === 'html' || label === 'handlebars' || label === 'razor') {
                    return new htmlWorker.default()
                }
                if (label === 'typescript' || label === 'javascript') {
                    return new tsWorker.default()
                }
                return new editorWorker.default()
            }
        };

        this.container.innerHTML = ''; // Clear loading

        this.editor = monaco.editor.create(this.container, {
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
            cursorBlinking: 'blink',
            cursorSmoothCaretAnimation: 'off',
            smoothScrolling: false,
            mouseWheelZoom: false,
        });

        // Listen for content changes to mark tabs dirty
        this.editor.onDidChangeModelContent(() => {
            if (this.activeTabId) {
                const tab = this.tabs.find(t => t.id === this.activeTabId);
                if (tab && !tab.isDirty) {
                    tab.isDirty = true;
                    this.renderTabBar();
                }
            }
        });
    }

    public setTabBarElement(element: HTMLElement) {
        this.tabBarElement = element;
    }

    private generateTabId(): string {
        return `tab_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    }

    private getLanguageFromPath(filePath: string): string {
        const ext = filePath.split('.').pop()?.toLowerCase() || '';
        const languageMap: Record<string, string> = {
            'js': 'javascript', 'jsx': 'javascript',
            'ts': 'typescript', 'tsx': 'typescript',
            'py': 'python', 'json': 'json',
            'html': 'html', 'htm': 'html',
            'css': 'css', 'scss': 'scss', 'less': 'less',
            'md': 'markdown', 'yaml': 'yaml', 'yml': 'yaml',
            'xml': 'xml', 'sql': 'sql', 'sh': 'shell', 'bash': 'shell',
            'rs': 'rust', 'go': 'go', 'java': 'java',
            'c': 'c', 'cpp': 'cpp', 'h': 'c', 'hpp': 'cpp',
            'rb': 'ruby', 'php': 'php', 'txt': 'plaintext',
        };
        return languageMap[ext] || 'plaintext';
    }

    private getFileIcon(filePath: string): string {
        const ext = filePath.split('.').pop()?.toLowerCase() || '';
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
            default:
                return '<i class="codicon codicon-file"></i>';
        }
    }

    /**
     * Open a file in a new tab or focus existing tab
     * Returns true if successful, false if tab limit reached and no tabs could be closed
     */
    public async openFile(filePath: string, content: string): Promise<boolean> {
        await this.ensureInitialized();
        if (!this.editor || !this.monaco) return false;

        // Check if file is already open
        const existingTab = this.tabs.find(t => t.path === filePath);
        if (existingTab) {
            this.switchTab(existingTab.id);
            // Update content if different
            const tabModel = this.tabModels.get(existingTab.id);
            if (tabModel && tabModel.model.getValue() !== content) {
                tabModel.model.setValue(content);
                existingTab.isDirty = false;
            }
            return true;
        }

        // Check tab limit
        if (this.tabs.length >= this.MAX_TABS) {
            // Try to close oldest non-dirty tab
            const nonDirtyTab = this.tabs.find(t => !t.isDirty);
            if (nonDirtyTab) {
                this.closeTab(nonDirtyTab.id);
            } else {
                // All tabs are dirty, cannot open new file
                return false;
            }
        }

        // Create new tab
        const tabId = this.generateTabId();
        const fileName = filePath.split('/').pop() || filePath;
        const language = this.getLanguageFromPath(filePath);

        const newTab: EditorTab = {
            id: tabId,
            path: filePath,
            name: fileName,
            isDirty: false,
        };

        // Create Monaco model for this tab
        const model = this.monaco.editor.createModel(content, language);
        this.tabModels.set(tabId, { model, viewState: null });

        this.tabs.push(newTab);
        this.switchTab(tabId);
        this.renderTabBar();

        return true;
    }

    /**
     * Switch to a tab by ID
     */
    public switchTab(tabId: string): void {
        if (!this.editor) return;

        const tab = this.tabs.find(t => t.id === tabId);
        if (!tab) return;

        // Save current view state
        if (this.activeTabId) {
            const currentTabModel = this.tabModels.get(this.activeTabId);
            if (currentTabModel) {
                currentTabModel.viewState = this.editor.saveViewState();
            }
        }

        // Switch to new tab
        this.activeTabId = tabId;
        const tabModel = this.tabModels.get(tabId);
        if (tabModel) {
            this.editor.setModel(tabModel.model);
            if (tabModel.viewState) {
                this.editor.restoreViewState(tabModel.viewState);
            }
        }

        this.onFileChanged(tab.path);
        this.renderTabBar();
    }

    /**
     * Close a tab by ID
     */
    public closeTab(tabId: string): void {
        if (!this.editor || !this.monaco) return;

        const tabIndex = this.tabs.findIndex(t => t.id === tabId);
        if (tabIndex === -1) return;

        // Dispose the Monaco model
        const tabModel = this.tabModels.get(tabId);
        if (tabModel) {
            tabModel.model.dispose();
            this.tabModels.delete(tabId);
        }

        // Remove tab from array
        this.tabs.splice(tabIndex, 1);

        // If this was the active tab, switch to another
        if (this.activeTabId === tabId) {
            if (this.tabs.length > 0) {
                // Switch to the previous tab, or the first one
                const newIndex = Math.min(tabIndex, this.tabs.length - 1);
                this.switchTab(this.tabs[newIndex].id);
            } else {
                this.activeTabId = null;
                // Show welcome screen
                this.editor.setModel(this.monaco.editor.createModel(
                    '// Welcome to SlowHands\n// Open a file to get started.',
                    'typescript'
                ));
                this.onFileChanged('');
            }
        }

        this.renderTabBar();
        this.onTabsChanged();
    }

    /**
     * Render the tab bar
     */
    public renderTabBar(): void {
        if (!this.tabBarElement) return;

        this.tabBarElement.innerHTML = '';

        if (this.tabs.length === 0) {
            this.tabBarElement.style.display = 'none';
            return;
        }

        this.tabBarElement.style.display = 'flex';

        this.tabs.forEach(tab => {
            const tabEl = document.createElement('div');
            tabEl.className = `tab${tab.id === this.activeTabId ? ' active' : ''}${tab.isDirty ? ' dirty' : ''}`;
            tabEl.dataset.tabId = tab.id;

            const iconHtml = this.getFileIcon(tab.path);
            const dirtyIndicator = tab.isDirty ? '<span class="dirty-indicator"></span>' : '';

            tabEl.innerHTML = `
                ${iconHtml}
                <span class="tab-name">${this.escapeHtml(tab.name)}</span>
                ${dirtyIndicator}
                <button class="tab-close" title="Close"><i class="codicon codicon-close"></i></button>
            `;

            // Click to switch tab
            tabEl.addEventListener('click', (e) => {
                const target = e.target as HTMLElement;
                if (!target.closest('.tab-close')) {
                    this.switchTab(tab.id);
                }
            });

            // Close button
            const closeBtn = tabEl.querySelector('.tab-close');
            closeBtn?.addEventListener('click', (e) => {
                e.stopPropagation();
                this.closeTab(tab.id);
            });

            this.tabBarElement!.appendChild(tabEl);
        });
    }

    private escapeHtml(text: string): string {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Get the current tabs
     */
    public getTabs(): EditorTab[] {
        return [...this.tabs];
    }

    /**
     * Get the active tab
     */
    public getActiveTab(): EditorTab | null {
        if (!this.activeTabId) return null;
        return this.tabs.find(t => t.id === this.activeTabId) || null;
    }

    /**
     * Check if we can open more tabs
     */
    public canOpenMoreTabs(): boolean {
        return this.tabs.length < this.MAX_TABS || this.tabs.some(t => !t.isDirty);
    }

    // ========================================
    // Legacy methods for compatibility
    // ========================================

    public async updateFile(filePath: string, content: string) {
        await this.openFile(filePath, content);
    }

    public getCurrentFilePath(): string | null {
        const activeTab = this.getActiveTab();
        return activeTab?.path || null;
    }

    public getCurrentContent(): string {
        return this.editor?.getValue() || '';
    }

    public markCurrentTabClean(): void {
        if (this.activeTabId) {
            const tab = this.tabs.find(t => t.id === this.activeTabId);
            if (tab) {
                tab.isDirty = false;
                this.renderTabBar();
            }
        }
    }

    // ========================================
    // Streaming support
    // ========================================

    public async streamContent(filePath: string, content: string, charsPerSecond: number = 60) {
        await this.ensureInitialized();
        if (!this.editor || !this.monaco) return;

        // First, open the file as a tab
        const fileName = filePath.split('/').pop() || filePath;
        const language = this.getLanguageFromPath(filePath);

        // Check if already open
        let tab = this.tabs.find(t => t.path === filePath);
        
        if (!tab) {
            // Need to open new tab
            if (this.tabs.length >= this.MAX_TABS) {
                const nonDirtyTab = this.tabs.find(t => !t.isDirty);
                if (nonDirtyTab) {
                    this.closeTab(nonDirtyTab.id);
                }
            }

            const tabId = this.generateTabId();
            tab = {
                id: tabId,
                path: filePath,
                name: fileName,
                isDirty: false,
            };

            const model = this.monaco.editor.createModel('', language);
            this.tabModels.set(tabId, { model, viewState: null });
            this.tabs.push(tab);
        }

        // Switch to this tab
        this.switchTab(tab.id);

        // Handle streaming state
        if (this.isStreaming && this.streamingTabId === tab.id) {
            this.pendingStreamContent = content;
            return;
        }

        if (this.streamingAbortController) {
            this.streamingAbortController.abort();
        }
        this.streamingAbortController = new AbortController();
        const signal = this.streamingAbortController.signal;

        this.streamingTabId = tab.id;
        this.isStreaming = true;
        this.isPaused = false;
        this.pendingStreamContent = null;
        this.currentStreamingContent = content;

        // Clear the model content
        const tabModel = this.tabModels.get(tab.id);
        if (tabModel) {
            tabModel.model.setValue('');
        }

        this.renderTabBar();

        const delayMs = 1000 / charsPerSecond;
        let currentContent = '';

        for (let i = 0; i < content.length; i++) {
            if (signal.aborted) break;
            while (this.isPaused && !signal.aborted) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            if (signal.aborted) break;

            currentContent += content[i];
            if (tabModel) {
                tabModel.model.setValue(currentContent);
            }

            const model = this.editor.getModel();
            const lineCount = model?.getLineCount() || 1;
            const lastLineLength = model?.getLineLength(lineCount) || 0;
            this.editor.setPosition({ lineNumber: lineCount, column: lastLineLength + 1 });
            this.editor.revealLine(lineCount);

            const char = content[i];
            let charDelay = delayMs;
            if (char === ' ' || char === '\t') charDelay = delayMs * 0.3;
            else if (char === '\n') charDelay = delayMs * 2;

            await new Promise(resolve => setTimeout(resolve, charDelay));
        }

        this.isPaused = false;
        this.isStreaming = false;
        this.streamingTabId = null;
        this.currentStreamingContent = null;

        if (this.pendingStreamContent !== null && tabModel) {
            tabModel.model.setValue(this.pendingStreamContent);
            this.pendingStreamContent = null;
        }

        // Mark tab as clean after streaming completes
        tab.isDirty = false;
        this.renderTabBar();
    }

    public stopStreaming() {
        if (this.streamingAbortController) {
            this.streamingAbortController.abort();
            this.streamingAbortController = null;
        }
        
        if (this.streamingTabId) {
            const tabModel = this.tabModels.get(this.streamingTabId);
            if (tabModel) {
                if (this.currentStreamingContent !== null) {
                    tabModel.model.setValue(this.currentStreamingContent);
                }
                if (this.pendingStreamContent !== null) {
                    tabModel.model.setValue(this.pendingStreamContent);
                }
            }
        }

        this.currentStreamingContent = null;
        this.pendingStreamContent = null;
        this.isStreaming = false;
        this.isPaused = false;
        this.streamingTabId = null;
    }

    public togglePause(): boolean {
        if (!this.isStreaming) return false;
        this.isPaused = !this.isPaused;
        return this.isPaused;
    }

    public getIsStreaming(): boolean {
        return this.isStreaming;
    }

    public getIsPaused(): boolean {
        return this.isPaused;
    }

    public layout(): void {
        if (this.editor) {
            this.editor.layout();
        }
    }
}
