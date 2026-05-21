# Design Document

## Architecture Overview

This design introduces shadcn/ui as the component primitive layer, adds react-router-dom for client-side routing, and builds a Chat Playground page with SSE streaming. The architecture follows an incremental migration strategy where existing custom Tailwind components are replaced one-at-a-time with shadcn equivalents while maintaining identical functionality.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│  BrowserRouter (react-router-dom)                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │  RootLayout (TopNav + Outlet)                     │  │
│  │  ┌─────────────┬──────────────┬────────────────┐  │  │
│  │  │ /           │ /graph       │ /playground     │  │  │
│  │  │ ThreePanel  │ KnowledgeGraph│ ChatPlayground │  │  │
│  │  │ (Explorer,  │              │ (Messages,     │  │  │
│  │  │  Viewer,    │              │  Stream,       │  │  │
│  │  │  Metadata)  │              │  Config)       │  │  │
│  │  └─────────────┴──────────────┴────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | React | 19 |
| Build | Vite | 8 |
| Styling | Tailwind CSS | 4 |
| Components | shadcn/ui | latest (new-york style) |
| Routing | react-router-dom | 7 |
| HTTP | axios | existing |
| Graph | reactflow | 11 |
| SSE | Native EventSource / fetch + ReadableStream | — |

---

## Component Architecture

### New Directory Structure

```
src/
├── api/
│   └── client.ts              # Extended with chat endpoints
├── components/
│   ├── ui/                    # shadcn/ui primitives (auto-generated)
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   ├── dropdown-menu.tsx
│   │   ├── input.tsx
│   │   ├── navigation-menu.tsx
│   │   ├── scroll-area.tsx
│   │   ├── select.tsx
│   │   ├── separator.tsx
│   │   ├── sheet.tsx
│   │   ├── skeleton.tsx
│   │   ├── textarea.tsx
│   │   └── badge.tsx
│   ├── Chat/
│   │   ├── ChatPlayground.tsx     # Page component
│   │   ├── MessageList.tsx        # Scrollable message container
│   │   ├── MessageBubble.tsx      # Individual message (user/assistant)
│   │   ├── TokenRenderer.tsx      # Progressive token display
│   │   ├── SourceAttribution.tsx  # Source badges with navigation
│   │   ├── ChatInput.tsx          # Input area + submit button
│   │   └── ChatConfig.tsx         # Retrieval mode, top_k, max_tokens
│   ├── FileExplorer/              # Existing (migrated to shadcn)
│   ├── FileViewer/                # Existing (migrated to shadcn)
│   ├── KnowledgeGraph/            # Existing (migrated to shadcn)
│   ├── Layout/
│   │   ├── RootLayout.tsx         # New: TopNav + Outlet wrapper
│   │   ├── TopNav.tsx             # Migrated to shadcn NavigationMenu
│   │   └── ThreePanel.tsx         # Migrated to shadcn ScrollArea
│   ├── MetadataSidebar/           # Existing (migrated to shadcn)
│   └── Search/                    # Existing (migrated to shadcn)
├── hooks/
│   ├── useChat.ts                 # New: chat state + streaming logic
│   ├── useFiles.ts                # Existing
│   ├── useGraph.ts                # Existing
│   └── useSync.ts                 # Existing
├── lib/
│   └── utils.ts                   # cn() utility
├── types/
│   └── index.ts                   # Extended with chat types
├── App.tsx                        # Router definition
├── index.css                      # Extended with shadcn CSS variables
└── main.tsx
```

---

## Interfaces and Data Models

### New TypeScript Types

```typescript
// Chat message types
interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming: boolean;
  isComplete: boolean;
  sources?: SourceAttribution[];
  metadata?: RetrievalMetadata;
  error?: string;
  timestamp: number;
}

interface SourceAttribution {
  fileId: number;
  fileName: string;
  department: string;
  chunkIndex: number;
}

interface RetrievalMetadata {
  retrievalMode: string;
  documentsRetrieved: number;
  queryTimeMs?: number;
  tokenUsage?: TokenUsage;
}

interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

// Chat request/response
interface ChatRequest {
  query: string;
  sessionId?: string;
  retrievalMode?: "local" | "global" | "combined";
  topK?: number;
  maxTokens?: number;
}

interface ChatResponse {
  answer: string;
  sourceAttributions: SourceAttribution[];
  retrievalMetadata: RetrievalMetadata;
  tokenUsage: TokenUsage;
  responseType: string;
  stepLimitReached: boolean;
}

// SSE event types
type SSEEvent =
  | { type: "token"; data: { content: string } }
  | { type: "sources"; data: { sourceAttributions: SourceAttribution[] } }
  | { type: "metadata"; data: RetrievalMetadata & { tokenUsage: TokenUsage } }
  | { type: "done"; data: Record<string, never> }
  | { type: "error"; data: { message: string } };

// Chat configuration state
interface ChatConfig {
  retrievalMode: "local" | "global" | "combined";
  topK?: number;
  maxTokens?: number;
}
```

---

## Component Design

### RootLayout

The root layout wraps all routes with the shared TopNav and provides the `<Outlet>` for child route rendering.

```typescript
// src/components/Layout/RootLayout.tsx
import { Outlet } from "react-router-dom";
import TopNav from "./TopNav";

export function RootLayout() {
  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <TopNav />
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
```

### Router Configuration

```typescript
// src/App.tsx
import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";
import { RootLayout } from "./components/Layout/RootLayout";
import { ExplorerPage } from "./pages/ExplorerPage";
import { GraphPage } from "./pages/GraphPage";
import { PlaygroundPage } from "./pages/PlaygroundPage";
import { SearchPage } from "./pages/SearchPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    children: [
      { index: true, element: <ExplorerPage /> },
      { path: "graph", element: <GraphPage /> },
      { path: "playground", element: <PlaygroundPage /> },
      { path: "search", element: <SearchPage /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
```

### useChat Hook

Manages chat state, session persistence, and SSE streaming.

```typescript
// src/hooks/useChat.ts
import { useState, useRef, useCallback } from "react";
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
    // Add user message immediately
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

  return { messages, isStreaming, config, setConfig, sendMessage, sessionId: sessionIdRef.current };
}
```

### Chat Stream Handler (API Client Extension)

```typescript
// Addition to src/api/client.ts

export async function sendChatMessage(body: ChatRequest): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>("/api/chat", body);
  return data;
}

export async function* streamChatMessage(
  body: ChatRequest,
  signal?: AbortSignal
): AsyncGenerator<SSEEvent> {
  const requestBody = transformKeys(body, camelToSnake);

  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(requestBody),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Stream request failed: ${response.status}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

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
      } else if (line.startsWith("data: ") && currentEvent) {
        const rawData = JSON.parse(line.slice(6));
        const data = transformKeys(rawData, snakeToCamel) as SSEEvent["data"];
        yield { type: currentEvent, data } as SSEEvent;
        currentEvent = "";
      }
    }
  }
}
```

### ChatPlayground Page

```typescript
// src/components/Chat/ChatPlayground.tsx
import { useChat } from "../../hooks/useChat";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { ChatConfig } from "./ChatConfig";
import { ScrollArea } from "../ui/scroll-area";
import { Card } from "../ui/card";

export function ChatPlayground() {
  const { messages, isStreaming, config, setConfig, sendMessage } = useChat();

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h1 className="text-lg font-semibold">Chat Playground</h1>
        <ChatConfig config={config} onChange={setConfig} />
      </div>

      <ScrollArea className="flex-1 p-4">
        <MessageList messages={messages} />
      </ScrollArea>

      <div className="border-t border-border p-4">
        <ChatInput onSubmit={sendMessage} disabled={isStreaming} />
      </div>
    </div>
  );
}
```

### Source Attribution Component

```typescript
// src/components/Chat/SourceAttribution.tsx
import { useNavigate } from "react-router-dom";
import { Badge } from "../ui/badge";
import type { SourceAttribution as SourceType } from "../../types";

interface Props {
  sources: SourceType[];
}

export function SourceAttribution({ sources }: Props) {
  const navigate = useNavigate();

  const handleClick = (source: SourceType) => {
    navigate(`/?fileId=${source.fileId}`);
  };

  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {sources.map((source, i) => (
        <Badge
          key={i}
          variant="secondary"
          className="cursor-pointer hover:bg-muted"
          onClick={() => handleClick(source)}
        >
          {source.fileName} · {source.department} · chunk {source.chunkIndex}
        </Badge>
      ))}
    </div>
  );
}
```

---

## Theming Strategy

### CSS Variable Mapping

The existing surface palette maps to shadcn/ui's CSS variable system:

```css
/* src/index.css — shadcn dark theme variables */
:root {
  --background: 228 12% 12%;       /* surface: #1a1b23 */
  --foreground: 220 10% 85%;       /* gray-200 text */

  --card: 228 10% 17%;             /* surface-100: #2a2b35 */
  --card-foreground: 220 10% 85%;

  --muted: 228 9% 20%;             /* surface-200: #32333f */
  --muted-foreground: 220 8% 55%;

  --popover: 228 10% 17%;          /* surface-100 */
  --popover-foreground: 220 10% 85%;

  --border: 228 8% 25%;            /* surface-300: #3a3b49 */
  --input: 228 8% 25%;

  --primary: 239 84% 67%;          /* primary: #6366f1 */
  --primary-foreground: 0 0% 100%;

  --secondary: 228 9% 20%;         /* surface-200 */
  --secondary-foreground: 220 10% 85%;

  --accent: 187 92% 53%;           /* accent: #22d3ee */
  --accent-foreground: 0 0% 0%;

  --destructive: 0 84% 60%;        /* danger: #ef4444 */
  --destructive-foreground: 0 0% 100%;

  --ring: 239 84% 67%;             /* primary */
  --radius: 0.5rem;
}
```

### cn() Utility

```typescript
// src/lib/utils.ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
```

---

## SSE Streaming Architecture

### Event Flow

```
User submits query
       │
       ▼
┌─────────────────┐     POST /api/chat/stream     ┌──────────────┐
│  ChatPlayground │ ─────────────────────────────► │   Backend    │
│                 │                                │              │
│  useChat hook   │ ◄─── SSE: event: token ─────── │  LangChain   │
│       │         │ ◄─── SSE: event: token ─────── │  Streaming   │
│       │         │ ◄─── SSE: event: sources ───── │              │
│       │         │ ◄─── SSE: event: metadata ──── │              │
│       │         │ ◄─── SSE: event: done ──────── │              │
│       ▼         │                                └──────────────┘
│  TokenRenderer  │
│  (progressive)  │
└─────────────────┘
```

### Error Handling Strategy

| Scenario | Behavior |
|----------|----------|
| SSE `error` event | Display error inline in message bubble, re-enable input |
| Network disconnect | Detect via ReadableStream close, show connection error toast |
| HTTP 422 | Show validation error before stream starts |
| HTTP 503 | Show "LLM not configured" message |
| Abort (user navigates away) | Cancel via AbortController, no error shown |

---

## Responsive Layout Strategy

| Breakpoint | Layout Behavior |
|-----------|-----------------|
| ≥ 1024px | Full three-panel layout with all panels visible |
| 768–1023px | Three-panel with collapsible side panels (toggle buttons) |
| < 768px | Single column; side panels accessible via shadcn Sheet/Drawer |

The Chat Playground always renders as a single-column layout regardless of viewport width.

---

## Migration Strategy

### Incremental Approach

1. **Phase 1**: Install shadcn/ui, add `cn()` utility, configure CSS variables
2. **Phase 2**: Add routing (RootLayout, page wrappers) — no visual changes
3. **Phase 3**: Build Chat Playground with shadcn primitives from scratch
4. **Phase 4**: Migrate existing components one-by-one (TopNav → FileExplorer → MetadataSidebar → etc.)

Each phase produces a working application. No big-bang rewrite.

### Component Migration Order

1. `TopNav` → shadcn NavigationMenu + Button + DropdownMenu
2. `ThreePanel` → shadcn ScrollArea for panels
3. `FileExplorer` → shadcn ScrollArea + Button + Input
4. `MetadataSidebar` → shadcn Card + Badge + Input
5. `SearchResults` → shadcn Card + Skeleton
6. `FileViewer` → shadcn Card + ScrollArea
7. Dialogs/Modals → shadcn Dialog

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Class merging utility resolves conflicts

For any set of Tailwind CSS class strings passed to `cn()`, the output SHALL be a single string where conflicting utility classes are resolved (last wins) and duplicate classes are removed.

**Validates: Requirements 1.3**

### Property 2: Undefined routes redirect to root

For any URL path that does not match one of the defined routes ("/", "/graph", "/playground", "/search"), navigating to that path SHALL result in a redirect to "/".

**Validates: Requirements 2.6**

### Property 3: Chat request includes all configured parameters

For any submitted chat query with a given configuration (retrievalMode, topK, maxTokens), the outgoing request body SHALL include the query text, the current session_id, and all non-undefined configuration values with correct field names.

**Validates: Requirements 3.3, 5.3**

### Property 4: Session ID uniqueness and format validity

For any number of generated session IDs, each SHALL be a valid UUID v4 string and no two SHALL be equal.

**Validates: Requirements 3.4**

### Property 5: User message immediate display

For any non-empty query string submitted by the user, the message SHALL appear in the Message_List before the streaming response begins (i.e., before any SSE events are received).

**Validates: Requirements 3.5**

### Property 6: Token accumulation produces correct message

For any sequence of "token" SSE events with content strings [t₁, t₂, ..., tₙ], the final assistant message content SHALL equal the concatenation t₁ + t₂ + ... + tₙ.

**Validates: Requirements 4.1**

### Property 7: Source attribution rendering completeness

For any source attribution object containing fileId, fileName, department, and chunkIndex, the rendered Source_Attribution_Panel SHALL display all three user-visible fields (fileName, department, chunkIndex) for every source in the list.

**Validates: Requirements 4.2, 6.2**

### Property 8: Metadata storage preservation

For any valid "metadata" SSE event payload containing retrievalMode, documentsRetrieved, and tokenUsage, the stored metadata on the assistant message SHALL contain all fields with identical values.

**Validates: Requirements 4.3**

### Property 9: Error event inline display

For any "error" SSE event with a message string, the Chat_Playground SHALL render that exact message string within the assistant message area and the submit button SHALL be enabled.

**Validates: Requirements 4.5**

### Property 10: Numeric parameter validation

For any integer value provided to the top_k input, it SHALL be accepted if and only if it is in the range [1, 50]. For any integer value provided to the max_tokens input, it SHALL be accepted if and only if it is in the range [1000, 16000].

**Validates: Requirements 5.4, 5.5**

### Property 11: Source attribution navigation

For any source attribution with a fileId, clicking that source SHALL navigate the application to the file explorer view with that specific fileId selected.

**Validates: Requirements 6.1**

### Property 12: Case transformation round-trip

For any object with single-depth camelCase keys, applying camelToSnake followed by snakeToCamel SHALL produce an object with keys identical to the original. Conversely, for any object with single-depth snake_case keys, applying snakeToCamel followed by camelToSnake SHALL produce identical keys.

**Validates: Requirements 9.3, 9.4**
