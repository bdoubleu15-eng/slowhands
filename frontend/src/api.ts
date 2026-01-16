import { WSMessage, WSMessageBase, FileItem } from './types';

// Session state for resumable connections
interface SessionState {
    sessionId: string;
    lastCorrelationId: string | null;
    createdAt: number;
}

const SESSION_STORAGE_KEY = 'slowhands_session';

export class APIClient {
    private websocket: WebSocket | null = null;
    private messageQueue: WSMessageBase[] = [];
    private reconnectAttempts = 0;
    private readonly MAX_RECONNECT_ATTEMPTS = 5;
    private readonly MAX_QUEUE_SIZE = 50;
    
    // Ping/Pong tracking
    private lastPingSentAt: number | null = null;
    public lastPingLatencyMs: number | null = null;
    private pingInterval: number | null = null;
    
    // Session tracking
    private sessionState: SessionState | null = null;
    private readonly SESSION_EXPIRY_MS = 60 * 60 * 1000; // 1 hour

    constructor(
        private readonly apiUrl: string,
        private readonly wsUrl: string,
        private readonly onMessage: (msg: WSMessage) => void,
        private readonly onStatusChange: (connected: boolean) => void,
        private readonly onLog: (text: string) => void
    ) {
        // Load session from storage on init
        this.loadSession();
    }

    public async fetchFiles(): Promise<FileItem[]> {
        try {
            const response = await fetch(`${this.apiUrl}/api/files`);
            if (!response.ok) throw new Error('Failed to fetch files');
            const data = await response.json();
            return data.files || [];
        } catch (e) {
            console.error('Error fetching workspace files:', e);
            return [];
        }
    }

    public async openWorkspace(folderPath: string): Promise<{ files: FileItem[]; workspace: string }> {
        const response = await fetch(`${this.apiUrl}/api/workspace/open`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_path: folderPath })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to open workspace');
        }
        
        return await response.json();
    }

    public async getWorkspace(): Promise<string | null> {
        try {
            const response = await fetch(`${this.apiUrl}/api/workspace`);
            if (!response.ok) return null;
            const data = await response.json();
            return data.workspace || null;
        } catch (e) {
            console.error('Error getting workspace:', e);
            return null;
        }
    }

    public async readFile(filePath: string): Promise<{ content: string; path: string }> {
        const response = await fetch(`${this.apiUrl}/api/files/${encodeURIComponent(filePath)}`);
        if (!response.ok) throw new Error('Failed to read file');
        return await response.json();
    }

    // ============================================
    // Session Management
    // ============================================

    private loadSession(): void {
        try {
            const stored = localStorage.getItem(SESSION_STORAGE_KEY);
            if (stored) {
                const session = JSON.parse(stored) as SessionState;
                // Check if session is expired
                if (Date.now() - session.createdAt < this.SESSION_EXPIRY_MS) {
                    this.sessionState = session;
                    console.debug('Loaded existing session:', session.sessionId);
                } else {
                    // Session expired, remove it
                    localStorage.removeItem(SESSION_STORAGE_KEY);
                    console.debug('Session expired, removed from storage');
                }
            }
        } catch (e) {
            console.error('Error loading session:', e);
            localStorage.removeItem(SESSION_STORAGE_KEY);
        }
    }

    private saveSession(): void {
        if (this.sessionState) {
            try {
                localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(this.sessionState));
            } catch (e) {
                console.error('Error saving session:', e);
            }
        }
    }

    private updateLastCorrelationId(correlationId: string): void {
        if (this.sessionState) {
            this.sessionState.lastCorrelationId = correlationId;
            this.saveSession();
        }
    }

    public getSessionId(): string | null {
        return this.sessionState?.sessionId || null;
    }

    // ============================================
    // WebSocket Connection
    // ============================================

    public connect(): void {
        if (this.websocket?.readyState === WebSocket.OPEN) return;

        this.onLog('Connecting to agent...');
        this.websocket = new WebSocket(this.wsUrl);

        this.websocket.onopen = () => {
            this.reconnectAttempts = 0;
            this.onLog('Connected to agent.');
            this.onStatusChange(true);
            
            // Start heartbeat
            this.startHeartbeat();
            
            // Try to resume session or create new one
            this.resumeSession();

            // Process queue after session resume
            if (this.messageQueue.length > 0) {
                this.onLog(`Sending ${this.messageQueue.length} queued message(s)...`);
                this.processMessageQueue();
            }
        };

        this.websocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === 'pong') {
                    this.handlePong();
                } else if (data.type === 'session_state') {
                    this.handleSessionState(data);
                } else {
                    // Track correlation ID for session resume
                    if (data.correlation_id) {
                        this.updateLastCorrelationId(data.correlation_id);
                    }
                    this.onMessage(data);
                }
            } catch (e) {
                console.error('Failed to parse message:', e);
            }
        };

        this.websocket.onclose = () => {
            this.onStatusChange(false);
            this.stopHeartbeat();
            
            // Reconnect logic
            if (this.reconnectAttempts < this.MAX_RECONNECT_ATTEMPTS) {
                this.reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 5000);
                this.onLog(`Reconnecting in ${delay/1000}s... (attempt ${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS})`);
                setTimeout(() => this.connect(), delay);
            } else {
                this.onLog('Connection failed. Start the server.');
            }
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    public disconnect(): void {
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
    }

    public send(message: WSMessageBase): void {
        if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
            this.queueMessage(message);
            // Try to connect if not already
            if (!this.websocket || this.websocket.readyState === WebSocket.CLOSED) {
                this.connect();
            }
            return;
        }

        try {
            this.websocket.send(JSON.stringify(message));
        } catch (e) {
            console.error('Error sending message:', e);
            this.queueMessage(message);
        }
    }

    private queueMessage(message: WSMessageBase): void {
        if (this.messageQueue.length >= this.MAX_QUEUE_SIZE) {
            this.onLog('Message queue full. Dropping oldest message.');
            this.messageQueue.shift();
        }
        this.messageQueue.push(message);
    }

    private processMessageQueue(): void {
        while (this.messageQueue.length > 0 && this.websocket?.readyState === WebSocket.OPEN) {
            const message = this.messageQueue.shift();
            if (message) {
                try {
                    this.websocket.send(JSON.stringify(message));
                } catch (e) {
                    this.messageQueue.unshift(message);
                    break;
                }
            }
        }
    }

    private resumeSession(): void {
        if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) return;
        
        // Send resume_session message
        const resumeMessage: any = {
            type: 'resume_session',
            session_id: this.sessionState?.sessionId || '',
            last_correlation_id: this.sessionState?.lastCorrelationId || null
        };
        
        try {
            this.websocket.send(JSON.stringify(resumeMessage));
            if (this.sessionState) {
                this.onLog('Resuming session...');
            }
        } catch (e) {
            console.error('Error sending resume session:', e);
        }
    }

    private handleSessionState(data: any): void {
        const sessionId = data.session_id;
        const isNew = data.is_new;
        const agentRunning = data.agent_running;
        const pendingMessages = data.pending_messages || 0;
        
        if (isNew) {
            // New session created
            this.sessionState = {
                sessionId,
                lastCorrelationId: null,
                createdAt: Date.now()
            };
            this.saveSession();
            this.onLog(`New session: ${sessionId.slice(0, 12)}...`);
        } else {
            // Existing session resumed
            if (this.sessionState) {
                this.sessionState.sessionId = sessionId;
            } else {
                this.sessionState = {
                    sessionId,
                    lastCorrelationId: data.last_correlation_id,
                    createdAt: Date.now()
                };
            }
            this.saveSession();
            
            if (pendingMessages > 0) {
                this.onLog(`Session resumed. Replaying ${pendingMessages} message(s)...`);
            } else {
                this.onLog(`Session resumed: ${sessionId.slice(0, 12)}...`);
            }
            
            if (agentRunning) {
                this.onLog('Agent is still running from previous session.');
            }
        }
    }

    // ============================================
    // Heartbeat
    // ============================================

    private startHeartbeat(): void {
        this.stopHeartbeat();
        this.pingInterval = window.setInterval(() => {
            if (this.websocket?.readyState === WebSocket.OPEN) {
                this.lastPingSentAt = Date.now();
                this.websocket.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    }

    private stopHeartbeat(): void {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    private handlePong(): void {
        if (this.lastPingSentAt !== null) {
            this.lastPingLatencyMs = Date.now() - this.lastPingSentAt;
            this.lastPingSentAt = null;
            console.debug(`Ping latency: ${this.lastPingLatencyMs}ms`);
        }
    }

    // ============================================
    // Utilities
    // ============================================

    public generateCorrelationId(): string {
        return `fe_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
    }

    public clearSession(): void {
        this.sessionState = null;
        localStorage.removeItem(SESSION_STORAGE_KEY);
        this.onLog('Session cleared.');
    }
}
