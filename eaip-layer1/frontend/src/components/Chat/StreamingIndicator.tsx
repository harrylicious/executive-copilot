/**
 * Animated typing indicator shown while the assistant is streaming a response.
 */
export function StreamingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1" aria-label="Generating response">
      <span className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce [animation-delay:0ms]" />
      <span className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce [animation-delay:150ms]" />
      <span className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce [animation-delay:300ms]" />
    </div>
  );
}
