// Shared Type Definitions

export interface FileItem {
    name: string;
    path: string;
    type: 'file' | 'directory';
    size?: number;
    children?: FileItem[];
}

// WebSocket Messages

export interface WSMessageBase {
    type: string;
    correlation_id?: string;
}

export interface WSChatMessage extends WSMessageBase {
    type: 'chat';
    content: string;
}

export interface WSStopMessage extends WSMessageBase {
    type: 'stop';
}

export interface WSPingMessage extends WSMessageBase {
    type: 'ping';
}

export interface WSOpenFileMessage extends WSMessageBase {
    type: 'open_file';
    path: string;
}

export interface WSFileContentMessage extends WSMessageBase {
    type: 'file_content';
    path: string;
    content: string;
    size: number;
    lines: number;
}

export interface WSPongMessage extends WSMessageBase {
    type: 'pong';
}

export interface FileOp {
    action: 'read' | 'write';
    path: string;
    content: string;
}

export interface WSStepMessage extends WSMessageBase {
    type: 'step';
    step_number: number;
    phase: 'think' | 'act' | 'respond';
    content: string;
    tool_name?: string;
    tool_success?: boolean;
    file_op?: FileOp; // Not in Pydantic model but added by AgentService
}

export interface WSCompleteMessage extends WSMessageBase {
    type: 'complete';
    step_number: number;
    phase: 'complete';
    content: string;
}

export interface WSErrorMessage extends WSMessageBase {
    type: 'error';
    step_number: number;
    phase: 'error';
    content: string;
}

export interface WSStoppedMessage extends WSMessageBase {
    type: 'stopped';
    step_number: number;
    phase: 'stopped';
    content: string;
}

export type WSMessage = 
    | WSChatMessage
    | WSStopMessage
    | WSPingMessage
    | WSOpenFileMessage
    | WSFileContentMessage
    | WSPongMessage
    | WSStepMessage
    | WSCompleteMessage
    | WSErrorMessage
    | WSStoppedMessage;
