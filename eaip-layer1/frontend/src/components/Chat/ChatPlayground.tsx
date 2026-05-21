import { useChat } from "@/hooks/useChat";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { ChatConfig } from "./ChatConfig";
import { PredefinedPrompts } from "./PredefinedPrompts";
import { Bot } from "lucide-react";

export function ChatPlayground() {
  const { messages, isStreaming, config, setConfig, sendMessage } = useChat();

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
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
  );
}
