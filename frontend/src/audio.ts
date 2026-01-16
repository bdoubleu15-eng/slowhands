/**
 * Audio Capture Module for Push-to-Talk
 *
 * Uses Web Audio API and MediaRecorder to capture microphone input
 * and export WAV audio for transcription.
 */

export interface AudioCaptureConfig {
    sampleRate?: number;
    channels?: number;
}

export interface AudioCaptureResult {
    blob: Blob;
    duration: number;
    sampleRate: number;
}

type RecordingStateChangeCallback = (isRecording: boolean) => void;
type AudioDataCallback = (result: AudioCaptureResult) => void;
type ErrorCallback = (error: Error) => void;

export class AudioCapture {
    private mediaRecorder: MediaRecorder | null = null;
    private audioChunks: Blob[] = [];
    private stream: MediaStream | null = null;
    private startTime: number = 0;
    private config: Required<AudioCaptureConfig>;

    private onStateChange: RecordingStateChangeCallback | null = null;
    private onAudioData: AudioDataCallback | null = null;
    private onError: ErrorCallback | null = null;

    constructor(config: AudioCaptureConfig = {}) {
        this.config = {
            sampleRate: config.sampleRate || 16000,  // 16kHz is good for speech
            channels: config.channels || 1,  // Mono
        };
    }

    /**
     * Set callback for recording state changes
     */
    public setOnStateChange(callback: RecordingStateChangeCallback): void {
        this.onStateChange = callback;
    }

    /**
     * Set callback for when audio data is ready
     */
    public setOnAudioData(callback: AudioDataCallback): void {
        this.onAudioData = callback;
    }

    /**
     * Set callback for errors
     */
    public setOnError(callback: ErrorCallback): void {
        this.onError = callback;
    }

    /**
     * Check if the browser supports audio recording
     */
    public static isSupported(): boolean {
        return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
    }

    /**
     * Request microphone permission
     */
    public async requestPermission(): Promise<boolean> {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: this.config.channels,
                    sampleRate: this.config.sampleRate,
                    echoCancellation: true,
                    noiseSuppression: true,
                }
            });

            // Stop the stream immediately - we just wanted to check permission
            stream.getTracks().forEach(track => track.stop());

            return true;
        } catch (error) {
            console.error('Microphone permission denied:', error);
            return false;
        }
    }

    /**
     * Start recording audio
     */
    public async startRecording(): Promise<void> {
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            console.warn('Already recording');
            return;
        }

        try {
            // Get microphone stream
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: this.config.channels,
                    sampleRate: this.config.sampleRate,
                    echoCancellation: true,
                    noiseSuppression: true,
                }
            });

            // Reset chunks
            this.audioChunks = [];
            this.startTime = Date.now();

            // Create MediaRecorder with WAV-compatible format
            // Note: Most browsers support webm/opus, we'll convert to WAV on export
            const mimeType = this.getSupportedMimeType();

            this.mediaRecorder = new MediaRecorder(this.stream, {
                mimeType: mimeType,
            });

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            this.mediaRecorder.onstop = async () => {
                const duration = (Date.now() - this.startTime) / 1000;

                // Convert to WAV
                const audioBlob = new Blob(this.audioChunks, { type: mimeType });

                try {
                    const wavBlob = await this.convertToWav(audioBlob);

                    if (this.onAudioData) {
                        this.onAudioData({
                            blob: wavBlob,
                            duration: duration,
                            sampleRate: this.config.sampleRate,
                        });
                    }
                } catch (error) {
                    if (this.onError) {
                        this.onError(error instanceof Error ? error : new Error(String(error)));
                    }
                }

                // Clean up stream
                if (this.stream) {
                    this.stream.getTracks().forEach(track => track.stop());
                    this.stream = null;
                }
            };

            this.mediaRecorder.onerror = (event) => {
                if (this.onError) {
                    this.onError(new Error(`MediaRecorder error: ${event}`));
                }
            };

            // Start recording with timeslice for chunked data
            this.mediaRecorder.start(100);  // Get data every 100ms

            if (this.onStateChange) {
                this.onStateChange(true);
            }

        } catch (error) {
            if (this.onError) {
                this.onError(error instanceof Error ? error : new Error(String(error)));
            }
            throw error;
        }
    }

    /**
     * Stop recording and get the audio data
     */
    public stopRecording(): void {
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();

            if (this.onStateChange) {
                this.onStateChange(false);
            }
        }
    }

    /**
     * Check if currently recording
     */
    public isRecording(): boolean {
        return this.mediaRecorder?.state === 'recording';
    }

    /**
     * Get a supported MIME type for recording
     */
    private getSupportedMimeType(): string {
        const types = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/ogg;codecs=opus',
            'audio/mp4',
        ];

        for (const type of types) {
            if (MediaRecorder.isTypeSupported(type)) {
                return type;
            }
        }

        return 'audio/webm';  // Fallback
    }

    /**
     * Convert audio blob to WAV format
     */
    private async convertToWav(audioBlob: Blob): Promise<Blob> {
        // Create audio context for decoding
        const audioContext = new AudioContext({ sampleRate: this.config.sampleRate });

        try {
            // Decode the audio
            const arrayBuffer = await audioBlob.arrayBuffer();
            const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

            // Convert to WAV
            const wavBuffer = this.audioBufferToWav(audioBuffer);

            return new Blob([wavBuffer], { type: 'audio/wav' });
        } finally {
            await audioContext.close();
        }
    }

    /**
     * Convert AudioBuffer to WAV ArrayBuffer
     */
    private audioBufferToWav(audioBuffer: AudioBuffer): ArrayBuffer {
        const numChannels = audioBuffer.numberOfChannels;
        const sampleRate = audioBuffer.sampleRate;
        const format = 1;  // PCM
        const bitDepth = 16;

        // Get channel data
        const channels: Float32Array[] = [];
        for (let i = 0; i < numChannels; i++) {
            channels.push(audioBuffer.getChannelData(i));
        }

        // Interleave channels
        const length = channels[0].length;
        const interleaved = new Float32Array(length * numChannels);

        for (let i = 0; i < length; i++) {
            for (let ch = 0; ch < numChannels; ch++) {
                interleaved[i * numChannels + ch] = channels[ch][i];
            }
        }

        // Create WAV file
        const dataLength = interleaved.length * (bitDepth / 8);
        const buffer = new ArrayBuffer(44 + dataLength);
        const view = new DataView(buffer);

        // WAV header
        this.writeString(view, 0, 'RIFF');
        view.setUint32(4, 36 + dataLength, true);
        this.writeString(view, 8, 'WAVE');
        this.writeString(view, 12, 'fmt ');
        view.setUint32(16, 16, true);  // Subchunk1Size
        view.setUint16(20, format, true);  // AudioFormat
        view.setUint16(22, numChannels, true);  // NumChannels
        view.setUint32(24, sampleRate, true);  // SampleRate
        view.setUint32(28, sampleRate * numChannels * (bitDepth / 8), true);  // ByteRate
        view.setUint16(32, numChannels * (bitDepth / 8), true);  // BlockAlign
        view.setUint16(34, bitDepth, true);  // BitsPerSample
        this.writeString(view, 36, 'data');
        view.setUint32(40, dataLength, true);

        // Write audio data
        const offset = 44;
        for (let i = 0; i < interleaved.length; i++) {
            // Clamp and convert to 16-bit
            const sample = Math.max(-1, Math.min(1, interleaved[i]));
            const intSample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
            view.setInt16(offset + i * 2, intSample, true);
        }

        return buffer;
    }

    /**
     * Write string to DataView
     */
    private writeString(view: DataView, offset: number, str: string): void {
        for (let i = 0; i < str.length; i++) {
            view.setUint8(offset + i, str.charCodeAt(i));
        }
    }

    /**
     * Clean up resources
     */
    public dispose(): void {
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
        }

        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }

        this.mediaRecorder = null;
        this.audioChunks = [];
    }
}
