/**
 * WebSocket collaboration client.
 *
 * Speaks the protocol documented in section 12 (join_room, document_update,
 * presence_update, ping). When no websocket URL is configured the client runs
 * in "local" mode: it reports a connected state and echoes nothing, so the UI
 * is fully functional before the backend exists.
 */
import type { CanvasOperation, ClientMessage, ConnectionState, ServerMessage } from "./types";

export interface RealtimeHandlers {
  onMessage: (msg: ServerMessage) => void;
  onConnectionState: (state: ConnectionState) => void;
}

export class RealtimeClient {
  private ws: WebSocket | null = null;
  private retries = 0;
  private closed = false;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private queue: ClientMessage[] = [];

  constructor(
    private url: string,
    private sessionId: string,
    private token: string,
    private handlers: RealtimeHandlers,
  ) {}

  connect() {
    if (!this.url) {
      // Local mode: no backend yet.
      this.handlers.onConnectionState("connected");
      return;
    }
    this.handlers.onConnectionState(this.retries === 0 ? "reconnecting" : "reconnecting");
    const ws = new WebSocket(this.url);
    this.ws = ws;

    ws.onopen = () => {
      this.retries = 0;
      this.handlers.onConnectionState("connected");
      this.send({ type: "join_room", protocol: 1, sessionId: this.sessionId, token: this.token });
      this.queue.splice(0).forEach((m) => this.send(m));
      this.pingTimer = setInterval(() => this.send({ type: "ping", protocol: 1 }), 20000);
    };

    ws.onmessage = (ev) => {
      try {
        this.handlers.onMessage(JSON.parse(ev.data as string) as ServerMessage);
      } catch {
        /* ignore malformed frame */
      }
    };

    ws.onclose = () => {
      if (this.pingTimer) clearInterval(this.pingTimer);
      if (this.closed) return;
      this.handlers.onConnectionState(this.retries > 4 ? "offline" : "reconnecting");
      const backoff = Math.min(500 * 2 ** this.retries++, 5000);
      setTimeout(() => this.connect(), backoff);
    };

    ws.onerror = () => ws.close();
  }

  send(msg: ClientMessage) {
    if (!this.url) return;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
    else if (msg.type === "document_update") this.queue.push(msg);
  }

  sendOps(ops: CanvasOperation[]) {
    this.send({
      type: "document_update",
      protocol: 1,
      sessionId: this.sessionId,
      operationId: crypto.randomUUID(),
      ops,
    });
  }

  sendPresence(cursor: { x: number; y: number } | null, selection: string[]) {
    this.send({ type: "presence_update", protocol: 1, sessionId: this.sessionId, cursor, selection });
  }

  disconnect() {
    this.closed = true;
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.ws?.close();
  }
}
