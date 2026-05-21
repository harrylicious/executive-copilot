import { useMemo } from "react";
import { marked } from "marked";
import { cn } from "@/lib/utils";
import { SourceAttribution } from "./SourceAttribution";
import { StreamingIndicator } from "./StreamingIndicator";
import { User, Bot, AlertCircle } from "lucide-react";
import type { ChatMessage } from "@/types";

// Configure marked for safe rendering
marked.setOptions({
  breaks: true,
  gfm: true,
});

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  const renderedContent = useMemo(() => {
    if (isUser || !message.content) return null;
    return marked.parse(message.content) as string;
  }, [message.content, isUser]);

  return (
    <div className={cn("flex gap-3 py-3", isUser ? "flex-row-reverse" : "flex-row")}>
      {/* Avatar */}
      <div
        className={cn(
          "shrink-0 w-7 h-7 rounded-full flex items-center justify-center mt-0.5",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-muted-foreground"
        )}
      >
        {isUser ? <User className="size-3.5" /> : <Bot className="size-3.5" />}
      </div>

      {/* Content */}
      <div className={cn("flex flex-col min-w-0 max-w-[85%]", isUser && "items-end")}>
        {/* Error state */}
        {message.error && (
          <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-destructive/10 border border-destructive/20">
            <AlertCircle className="size-3.5 text-destructive shrink-0" />
            <span className="text-xs text-destructive">{message.error}</span>
          </div>
        )}

        {/* User message */}
        {isUser && !message.error && (
          <div className="px-3 py-2 rounded-2xl rounded-tr-sm bg-primary text-primary-foreground">
            <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
          </div>
        )}

        {/* Assistant message with markdown */}
        {!isUser && !message.error && (
          <div className="space-y-2">
            {message.content ? (
              <div
                className="prose prose-sm dark:prose-invert max-w-none text-foreground prose-p:my-1.5 prose-headings:my-2 prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5 prose-pre:my-2 prose-code:text-xs prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-muted prose-pre:border prose-pre:border-border prose-a:text-primary prose-blockquote:border-primary/30"
                dangerouslySetInnerHTML={{ __html: renderedContent || "" }}
              />
            ) : null}

            {/* Streaming indicator */}
            {message.isStreaming && <StreamingIndicator />}

            {/* Sources */}
            {message.sources && message.sources.length > 0 && (
              <SourceAttribution sources={message.sources} />
            )}

            {/* Metadata */}
            {message.metadata && message.isComplete && (
              <div className="flex items-center gap-3 text-[10px] text-muted-foreground pt-1">
                {message.metadata.queryTimeMs && (
                  <span>{message.metadata.queryTimeMs}ms</span>
                )}
                {message.metadata.documentsRetrieved != null && (
                  <span>{message.metadata.documentsRetrieved} docs retrieved</span>
                )}
                {message.metadata.retrievalMode && (
                  <span className="capitalize">{message.metadata.retrievalMode}</span>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
