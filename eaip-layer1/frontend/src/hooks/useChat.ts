import { useState, useRef, useCallback, useEffect } from "react";
import { streamChatMessage } from "../api/client";
import type { ChatMessage, ChatConfig, SSEEvent } from "../types";

function generateSessionId(): string {
  return crypto.randomUUID();
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [config, setConfig] = useState<ChatConfig>({ retrievalMode: "combined" });
  const sessionIdRef = useRef<string>(generateSessionId());
  const abortRef = useRef<AbortController | null>(null);

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
    }
  }, [config]);

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

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  return { messages, isStreaming, config, setConfig, sendMessage, sessionId: sessionIdRef.current };
}
