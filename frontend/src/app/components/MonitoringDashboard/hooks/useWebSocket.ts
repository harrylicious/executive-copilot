import { useState, useEffect, useRef, useCallback } from "react";

// ─── Types ───────────────────────────────────────────────────────────────────

export type ConnectionState =
  | "connecting"
  | "connected"
  | "disconnected"
  | "reconnecting";

export interface WSMessage {
  event_type: string;
  payload: Record<string, unknown>;
  timestamp: string;
  event_id: number;
}

export interface UseWebSocketResult {
  messages: WSMessage[];
  connectionState: ConnectionState;
  lastEventId: number | null;
  isConnected: boolean;
  sendMessage: (data: unknown) => void;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;
const MAX_RETRIES = 10;

function getWebSocketUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  return `${protocol}//${host}/ws/embedding-status`;
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useWebSocket(): UseWebSocketResult {
  const [messages, setMessages] = useState<WSMessage[]>([]);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("disconnected");
  const [lastEventId, setLastEventId] = useState<number | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const backoffRef = useRef(INITIAL_BACKOFF_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastEventIdRef = useRef<number | null>(null);
  const mountedRef = useRef(true);

  // Keep ref in sync with state for use inside callbacks
  useEffect(() => {
    lastEventIdRef.current = lastEventId;
  }, [lastEventId]);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    clearReconnectTimer();

    const url = getWebSocketUrl();
    setConnectionState(
      retriesRef.current > 0 ? "reconnecting" : "connecting"
    );

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setConnectionState("connected");
      retriesRef.current = 0;
      backoffRef.current = INITIAL_BACKOFF_MS;

      // On reconnect, request missed events
      if (lastEventIdRef.current !== null) {
        ws.send(
          JSON.stringify({ last_event_id: lastEventIdRef.current })
        );
      }
    };

    ws.onmessage = (event: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        const parsed = JSON.parse(event.data) as WSMessage;
        if (parsed.event_id != null) {
          setLastEventId(parsed.event_id);
        }
        setMessages((prev) => [...prev, parsed]);
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      wsRef.current = null;
      setConnectionState("disconnected");
      scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will fire after onerror, so reconnect is handled there
      ws.close();
    };
  }, [clearReconnectTimer]);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;
    if (retriesRef.current >= MAX_RETRIES) {
      setConnectionState("disconnected");
      return;
    }

    setConnectionState("reconnecting");
    const delay = backoffRef.current;

    reconnectTimerRef.current = setTimeout(() => {
      retriesRef.current += 1;
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
      connect();
    }, delay);
  }, [connect]);

  const sendMessage = useCallback((data: unknown) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, clearReconnectTimer]);

  return {
    messages,
    connectionState,
    lastEventId,
    isConnected: connectionState === "connected",
    sendMessage,
  };
}
