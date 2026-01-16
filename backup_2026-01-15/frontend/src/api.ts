import { WSMessage, WSMessageBase, FileItem } from './types';

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

    constructor(
        private readonly apiUrl: string,
        private readonly wsUrl: string,
        private readonly onMessage: (msg: WSMessage) => void,
        private readonly onStatusChange: (connected: boolean) => void,
        private readonly onLog: (text: string) => void
    ) {}

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

    public async readFile(filePath: string): Promise<{ content: string; path: string }> {
        const response = await fetch(`${this.apiUrl}/api/files/${encodeURIComponent(filePath)}`);
        if (!response.ok) throw new Error('Failed to read file');
        return await response.json();
    }

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

            // Process queue
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
                } else {
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

    public generateCorrelationId(): string {
        return `fe_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
    }
}
