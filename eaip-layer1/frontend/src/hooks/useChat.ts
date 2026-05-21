import { useState, useRef, useCallback, useEffect } from "react";
import { streamChatMessage, saveSession, getSession } from "../api/client";
import type { ChatMessage, ChatConfig, SSEEvent, ChatMessageRecord } from "../types";

function generateSessionId(): string {
  return crypto.randomUUID();
}

/** Derive a short title from the first user message. */
function deriveTitle(content: string): string {
  const trimmed = content.trim();
  if (trimmed.length <= 50) return trimmed;
  return trimmed.slice(0, 47) + "...";
}

/** Convert frontend ChatMessage to the record shape expected by the API. */
function toMessageRecord(msg: ChatMessage, sessionId: string): ChatMessageRecord {
  return {
    id: msg.id,
    sessionId,
    role: msg.role,
    content: msg.content,
    sources: msg.sources ?? null,
    metadataJson: msg.metadata ?? null,
    error: msg.error ?? null,
    timestamp: msg.timestamp,
  };
}

/** Convert a persisted message record back to a frontend ChatMessage. */
function fromMessageRecord(record: ChatMessageRecord): ChatMessage {
  return {
    id: record.id,
    role: record.role,
    content: record.content,
    isStreaming: false,
    isComplete: true,
    sources: record.sources ?? undefined,
    metadata: record.metadataJson ?? undefined,
    error: record.error ?? undefined,
    timestamp: record.timestamp,
  };
}

export function useChat(initialSessionId?: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [config, setConfig] = useState<ChatConfig>({ retrievalMode: "combined" });
  const sessionIdRef = useRef<string>(initialSessionId || generateSessionId());
  const abortRef = useRef<AbortController | null>(null);
  const titleRef = useRef<string | null>(null);

  // Load an existing session from the database
  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const session = await getSession(sessionId);
      sessionIdRef.current = session.id;
      titleRef.current = session.title ?? null;

      if (session.retrievalMode || session.topK || session.maxTokens) {
        setConfig({
          retrievalMode: (session.retrievalMode as ChatConfig["retrievalMode"]) || "combined",
          topK: session.topK ?? undefined,
          maxTokens: session.maxTokens ?? undefined,
        });
      }

      setMessages(session.messages.map(fromMessageRecord));
    } catch {
      // Session not found — start fresh
      sessionIdRef.current = sessionId;
    }
  }, []);

  // Load session on mount if an initialSessionId was provided
  useEffect(() => {
    if (initialSessionId) {
      loadSession(initialSessionId);
    }
  }, [initialSessionId, loadSession]);

  // Persist the current session state to the database
  const persistSession = useCallback(
    async (msgs: ChatMessage[]) => {
      const sessionId = sessionIdRef.current;
      // Only persist if there are completed messages
      const completedMessages = msgs.filter((m) => m.isComplete && m.content.length > 0);
      if (completedMessages.length === 0) return;

      // Auto-generate title from first user message if not set
      if (!titleRef.current) {
        const firstUser = completedMessages.find((m) => m.role === "user");
        if (firstUser) {
          titleRef.current = deriveTitle(firstUser.content);
        }
      }

      try {
        await saveSession({
          id: sessionId,
          title: titleRef.current,
          retrievalMode: config.retrievalMode,
          topK: config.topK ?? null,
          maxTokens: config.maxTokens ?? null,
          messages: completedMessages.map((m) => toMessageRecord(m, sessionId)),
        });
      } catch (err) {
        console.error("Failed to persist session:", err);
      }
    },
    [config]
  );

  const sendMessage = useCallback(async (query: string) => {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: query,
      isStreaming: false,
      isComplete: true,
      timestamp: Date.now(),
    };

    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      isStreaming: true,
      isComplete: false,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const eventStream = await streamChatMessage(
        {
          query,
          sessionId: sessionIdRef.current,
          retrievalMode: config.retrievalMode,
          topK: config.topK,
          maxTokens: config.maxTokens,
        },
        controller.signal
      );

      for await (const event of eventStream) {
        handleSSEEvent(event, assistantMsg.id);
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsg.id
              ? { ...m, isStreaming: false, isComplete: true, error: "Connection lost" }
              : m
          )
        );
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;

      // Persist after streaming completes
      setMessages((prev) => {
        persistSession(prev);
        return prev;
      });
    }
  }, [config, persistSession]);

  const handleSSEEvent = (event: SSEEvent, msgId: string) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== msgId) return m;
        switch (event.type) {
          case "token":
            return { ...m, content: m.content + event.data.content };
          case "sources":
            return { ...m, sources: event.data.sourceAttributions };
          case "metadata":
            return { ...m, metadata: event.data };
          case "done":
            return { ...m, isStreaming: false, isComplete: true };
          case "error":
            return { ...m, isStreaming: false, isComplete: true, error: event.data.message };
          default:
            return m;
        }
      })
    );
  };

  const startNewSession = useCallback(() => {
    sessionIdRef.current = generateSessionId();
    titleRef.current = null;
    setMessages([]);
    setConfig({ retrievalMode: "combined" });
  }, []);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  return {
    messages,
    isStreaming,
    config,
    setConfig,
    sendMessage,
    sessionId: sessionIdRef.current,
    loadSession,
    startNewSession,
  };
}
