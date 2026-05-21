import { useChat } from "@/hooks/useChat";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { ChatConfig } from "./ChatConfig";
import { PredefinedPrompts } from "./PredefinedPrompts";
import { SessionList } from "./SessionList";
import { Bot, PanelLeftClose, PanelLeft, Plus } from "lucide-react";
import { useState, useCallback } from "react";

export function ChatPlayground() {
  const { messages, isStreaming, config, setConfig, sendMessage, loadSession, startNewSession } =
    useChat();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      loadSession(sessionId);
    },
    [loadSession]
  );

  const handleNewSession = useCallback(() => {
    startNewSession();
    setRefreshKey((k) => k + 1);
  }, [startNewSession]);

  return (
    <div className="flex h-full">
      {/* Session sidebar */}
      {sidebarOpen && (
        <div className="w-64 border-r border-border flex flex-col shrink-0">
          <div className="flex items-center justify-between px-3 py-2 border-b border-border">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Sessions
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={handleNewSession}
                className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
                title="New session"
              >
                <Plus className="size-3.5" />
              </button>
              <button
                onClick={() => setSidebarOpen(false)}
                className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
                title="Close sidebar"
              >
                <PanelLeftClose className="size-3.5" />
              </button>
            </div>
          </div>
          <SessionList
            onSelect={handleSelectSession}
            refreshKey={refreshKey}
          />
        </div>
      )}

      {/* Main chat area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground mr-1"
                title="Open sidebar"
              >
                <PanelLeft className="size-4" />
              </button>
            )}
            <Bot className="size-4 text-primary" />
            <h1 className="text-sm font-semibold">Playground</h1>
          </div>
          <ChatConfig config={config} onChange={setConfig} />
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-hidden">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center px-4">
              <div className="flex flex-col items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="size-5 text-primary" />
                </div>
                <p className="text-sm text-muted-foreground text-center max-w-sm">
                  Ask questions about your knowledge base. I'll search through your documents and provide answers with sources.
                </p>
              </div>
              <PredefinedPrompts onSelect={sendMessage} disabled={isStreaming} />
            </div>
          ) : (
            <MessageList messages={messages} />
          )}
        </div>

        {/* Input area */}
        <div className="border-t border-border p-3 shrink-0">
          {messages.length > 0 && (
            <div className="mb-2">
              <PredefinedPrompts onSelect={sendMessage} disabled={isStreaming} compact />
            </div>
          )}
          <ChatInput onSubmit={sendMessage} disabled={isStreaming} />
        </div>
      </div>
    </div>
  );
}
