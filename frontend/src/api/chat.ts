import { apiPost } from "./client";

export interface ChatSourceAttribution {
  file_id: number;
  file_name: string;
  department: string;
  chunk_index: number;
}

export interface ChatResponse {
  answer: string;
  source_attributions: ChatSourceAttribution[];
  retrieval_metadata: {
    retrieval_mode: string;
    documents_retrieved: number;
    query_time_ms: number;
  };
  token_usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  response_type: string;
  step_limit_reached: boolean;
}

export interface ChatRequest {
  query: string;
  session_id?: string;
  retrieval_mode?: "local" | "global" | "combined";
  top_k?: number;
  max_tokens?: number;
  language?: "id" | "en";
  nuance?: "formal" | "santai" | "profesional" | "ramah" | "tegas";
}

export async function sendChat(body: ChatRequest): Promise<ChatResponse> {
  return apiPost<ChatResponse>("/chat", body);
}

export type ChatStreamEvent =
  | { event: "token"; data: { content: string } }
  | { event: "sources"; data: { source_attributions: ChatSourceAttribution[] } }
  | { event: "metadata"; data: Record<string, unknown> }
  | { event: "done"; data: Record<string, never> }
  | { event: "suggestions"; data: { suggestions: string[] } }
  | { event: "error"; data: { message: string } };

/** Stream chat response via SSE. Calls onEvent for each parsed event. */
export async function streamChat(
  body: ChatRequest,
  onEvent: (evt: ChatStreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Chat stream failed (${res.status})`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      let currentEvent = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          const dataStr = line.slice(6);
          try {
            const data = JSON.parse(dataStr);
            onEvent({ event: currentEvent as ChatStreamEvent["event"], data });
          } catch {
            // skip unparseable data lines
          }
        }
      }
    }
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") return;
    throw err;
  }
}
