/**
 * WebSocket Client — Phase 8 Step 8.6.1
 * ========================================
 * Full-duplex WebSocket transport for QuantSight real-time data.
 *
 * Features:
 *   - Anonymous session tokens (persisted in sessionStorage)
 *   - Subscription filtering (team, player_id, game_id)
 *   - Exponential backoff reconnection (max 10 attempts)
 *   - Auto re-subscribe on reconnect
 *   - Annotation support
 *   - Type-safe event handlers
 *
 * Usage:
 *   import { wsClient } from '../services/wsClient';
 *   wsClient.connect();
 *   wsClient.subscribe({ team: 'LAL' });
 *   const unsub = wsClient.on('game_update', (data) => { ... });
 */

// ── Types ───────────────────────────────────────────────────────────────────

export interface WSMessage {
    type: string;
    data?: unknown;
    timestamp?: string;
    connection_id?: string;
    session_token?: string;
    server_time?: string;
    filters?: Record<string, string>;
    code?: string;
    message?: string;
}

type MessageHandler = (data: unknown) => void;

// ── Client ──────────────────────────────────────────────────────────────────

export class WebSocketClient {
    private ws: WebSocket | null = null;
    private reconnectAttempts = 0;
    private maxReconnects = 10;
    private baseDelay = 2000;
    private sessionToken: string;
    private messageHandlers: Map<string, Set<MessageHandler>> = new Map();
    private currentFilters: Record<string, string> = {};
    private _isConnected = false;
    private _reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    constructor() {
        // Persist anonymous session token in sessionStorage
        const stored = sessionStorage.getItem('qs_session_token');
        if (stored) {
            this.sessionToken = stored;
        } else {
            this.sessionToken = crypto.randomUUID();
            sessionStorage.setItem('qs_session_token', this.sessionToken);
        }
    }

    /** Establish WebSocket connection. */
    connect(): void {
        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            return; // Already connected/connecting
        }

        // Derive WebSocket URL from API base
        const apiBase = (import.meta as Record<string, Record<string, string>>).env?.VITE_PULSE_WS_URL
            || (import.meta as Record<string, Record<string, string>>).env?.VITE_API_BASE_URL?.replace('https://', 'wss://')
            || 'wss://quantsight-cloud-458498663186.us-central1.run.app';

        const url = new URL(`${apiBase}/live/ws`);
        url.searchParams.set('session_token', this.sessionToken);

        try {
            this.ws = new WebSocket(url.toString());
        } catch (err) {
            console.error('[wsClient] Failed to create WebSocket:', err);
            this._scheduleReconnect();
            return;
        }

        this.ws.onopen = () => {
            console.info('[wsClient] Connected');
            this._isConnected = true;
            this.reconnectAttempts = 0;

            // Re-apply active filters on reconnect
            if (Object.keys(this.currentFilters).length > 0) {
                this.subscribe(this.currentFilters);
            }
        };

        this.ws.onmessage = (event: MessageEvent) => {
            try {
                const msg: WSMessage = JSON.parse(event.data);

                // Handle server pings (heartbeat)
                if (msg.type === 'ping') {
                    this.send({ action: 'ping' });
                    return;
                }

                // Dispatch to registered handlers
                const handlers = this.messageHandlers.get(msg.type);
                if (handlers) {
                    handlers.forEach(h => {
                        try {
                            h(msg.data ?? msg);
                        } catch (err) {
                            console.error(`[wsClient] Handler error for ${msg.type}:`, err);
                        }
                    });
                }
            } catch {
                // Malformed message — ignore
            }
        };

        this.ws.onclose = (event: CloseEvent) => {
            this._isConnected = false;

            if (event.code === 1008) {
                // Connection limit or memory pressure — backoff longer
                console.warn('[wsClient] Server rejected (1008). Retrying in 60s.');
                this._reconnectTimer = setTimeout(() => this.connect(), 60_000);
                return;
            }

            if (event.code === 1013) {
                // Feature disabled
                console.info('[wsClient] WebSocket feature disabled on server.');
                return;
            }

            if (event.code === 1000) {
                // Normal close — no reconnect
                console.info('[wsClient] Disconnected normally.');
                return;
            }

            // Abnormal close — reconnect with backoff
            this._scheduleReconnect();
        };

        this.ws.onerror = () => {
            // onerror always followed by onclose — reconnect handled there
        };
    }

    /** Subscribe to filtered events. */
    subscribe(filters: Record<string, string>): void {
        this.currentFilters = filters;
        this.send({ action: 'subscribe', filters });
    }

    /** Unsubscribe from all filters. */
    unsubscribe(): void {
        this.currentFilters = {};
        this.send({ action: 'unsubscribe' });
    }

    /**
     * Register a handler for a specific event type.
     * Returns an unsubscribe function.
     */
    on(eventType: string, handler: MessageHandler): () => void {
        if (!this.messageHandlers.has(eventType)) {
            this.messageHandlers.set(eventType, new Set());
        }
        this.messageHandlers.get(eventType)!.add(handler);

        // Return unsubscribe function
        return () => {
            this.messageHandlers.get(eventType)?.delete(handler);
        };
    }

    /** Send an annotation. */
    annotate(contextType: string, contextId: string, content: string): void {
        this.send({
            action: 'annotate',
            context_type: contextType,
            context_id: contextId,
            content,
        });
    }

    /** Send a reaction. */
    react(contextType: string, contextId: string, noteId: string, reaction: string): void {
        this.send({
            action: 'react',
            context_type: contextType,
            context_id: contextId,
            note_id: noteId,
            reaction,
        });
    }

    /** Check if currently connected. */
    get isConnected(): boolean {
        return this._isConnected && this.ws?.readyState === WebSocket.OPEN;
    }

    /** Get the session token. */
    get token(): string {
        return this.sessionToken;
    }

    /** Close the connection permanently (no reconnect). */
    disconnect(): void {
        this.maxReconnects = 0;
        if (this._reconnectTimer) {
            clearTimeout(this._reconnectTimer);
            this._reconnectTimer = null;
        }
        this.ws?.close(1000, 'Client disconnect');
        this._isConnected = false;
    }

    // ── Private ───────────────────────────────────────────────────────────

    private send(data: unknown): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
        // If not open: message dropped silently. Reconnect will re-subscribe.
    }

    private _scheduleReconnect(): void {
        if (this.reconnectAttempts >= this.maxReconnects) {
            console.warn('[wsClient] Max reconnect attempts reached.');
            return;
        }

        const delay = Math.min(
            this.baseDelay * Math.pow(2, this.reconnectAttempts),
            60_000,
        );
        this.reconnectAttempts++;
        console.info(`[wsClient] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnects})`);
        this._reconnectTimer = setTimeout(() => this.connect(), delay);
    }
}

// ── Singleton Export ─────────────────────────────────────────────────────────

export const wsClient = new WebSocketClient();

export default wsClient;
