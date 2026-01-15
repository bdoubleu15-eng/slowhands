import * as monaco from 'monaco-editor'
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import jsonWorker from 'monaco-editor/esm/vs/language/json/json.worker?worker'
import cssWorker from 'monaco-editor/esm/vs/language/css/css.worker?worker'
import htmlWorker from 'monaco-editor/esm/vs/language/html/html.worker?worker'
import tsWorker from 'monaco-editor/esm/vs/language/typescript/ts.worker?worker'

// Configure Monaco Environment
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

export class EditorManager {
    private editor: monaco.editor.IStandaloneCodeEditor;
    private currentFilePath: string | null = null;
    
    // Streaming state
    private isStreaming = false;
    private isPaused = false;
    private streamingAbortController: AbortController | null = null;
    private streamingFilePath: string | null = null;
    private pendingStreamContent: string | null = null;
    private currentStreamingContent: string | null = null;

    constructor(container: HTMLElement) {
        this.editor = monaco.editor.create(container, {
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

    public updateFile(filePath: string, content: string) {
        this.currentFilePath = filePath;
        const language = this.getLanguageFromPath(filePath);
        const model = this.editor.getModel();
        if (model) {
            monaco.editor.setModelLanguage(model, language);
            this.editor.setValue(content);
        }
        this.onFileChanged(filePath);
    }

    public async streamContent(filePath: string, content: string, charsPerSecond: number = 60) {
        if (this.isStreaming && this.streamingFilePath === filePath) {
            this.pendingStreamContent = content;
            return;
        }

        if (this.streamingAbortController) {
            this.streamingAbortController.abort();
        }
        this.streamingAbortController = new AbortController();
        const signal = this.streamingAbortController.signal;

        this.currentFilePath = filePath;
        this.streamingFilePath = filePath;
        const language = this.getLanguageFromPath(filePath);

        const model = this.editor.getModel();
        if (model) {
            monaco.editor.setModelLanguage(model, language);
            this.editor.setValue('');
        }
        this.onFileChanged(filePath);

        this.isStreaming = true;
        this.isPaused = false;
        this.pendingStreamContent = null;
        this.currentStreamingContent = content;
        
        const delayMs = 1000 / charsPerSecond;
        let currentContent = '';

        for (let i = 0; i < content.length; i++) {
            if (signal.aborted) break;
            while (this.isPaused && !signal.aborted) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            if (signal.aborted) break;

            currentContent += content[i];
            this.editor.setValue(currentContent);

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
        this.streamingFilePath = null;
        this.currentStreamingContent = null;

        if (this.pendingStreamContent !== null) {
            this.editor.setValue(this.pendingStreamContent);
            this.pendingStreamContent = null;
        }
    }

    public stopStreaming() {
        if (this.streamingAbortController) {
            this.streamingAbortController.abort();
            this.streamingAbortController = null;
        }
        if (this.currentStreamingContent !== null) {
            this.editor.setValue(this.currentStreamingContent);
            this.currentStreamingContent = null;
        }
        if (this.pendingStreamContent !== null) {
            this.editor.setValue(this.pendingStreamContent);
            this.pendingStreamContent = null;
        }
        this.isStreaming = false;
        this.isPaused = false;
        this.streamingFilePath = null;
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
        this.editor.layout();
    }

    // Callback to be set by the UI manager
    public onFileChanged: (filePath: string) => void = () => {};
}
