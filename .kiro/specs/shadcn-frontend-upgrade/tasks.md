# Implementation Plan: shadcn Frontend Upgrade

## Overview

Incremental migration of the Executive Copilot frontend to shadcn/ui components, addition of client-side routing via react-router-dom, and implementation of a Chat Playground page with SSE streaming. The plan follows four phases: install/config → routing → chat playground → component migration. Each phase produces a working application.

## Tasks

- [x] 1. Install shadcn/ui and configure project foundations
  - [x] 1.1 Install shadcn/ui dependencies and initialize configuration
    - Install `clsx`, `tailwind-merge`, `class-variance-authority`, and `lucide-react`
    - Run shadcn/ui init with "new-york" style variant and Tailwind CSS 4 compatibility
    - Create `src/lib/utils.ts` with the `cn()` utility function
    - Create `components.json` configuration file for shadcn CLI
    - _Requirements: 1.1, 1.3_

  - [x] 1.2 Configure CSS variables and dark theme
    - Update `src/index.css` with shadcn/ui CSS variable definitions
    - Map existing surface-100/200/300 palette to `--background`, `--card`, `--muted` variables
    - Configure `--primary` (indigo), `--accent` (cyan), `--destructive` (red) variables
    - Set `--border`, `--ring`, `--radius` tokens
    - Ensure dark theme is the default appearance
    - _Requirements: 1.2, 8.1, 8.2, 8.4_

  - [x] 1.3 Install initial shadcn/ui component primitives
    - Add shadcn components: button, card, input, textarea, badge, scroll-area, select, separator, skeleton, dialog, dropdown-menu, navigation-menu, sheet
    - Verify components render correctly with the configured dark theme
    - _Requirements: 1.1, 7.2, 7.3, 7.4, 7.5, 7.7, 7.8_

  - [x]* 1.4 Write property test for cn() utility
    - **Property 1: Class merging utility resolves conflicts**
    - **Validates: Requirements 1.3**

- [x] 2. Checkpoint - Ensure the app builds and renders correctly
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Add client-side routing with react-router-dom
  - [x] 3.1 Create RootLayout component with TopNav and Outlet
    - Create `src/components/Layout/RootLayout.tsx`
    - Render existing TopNav at the top and `<Outlet>` for child routes
    - Apply `min-h-screen flex flex-col bg-background text-foreground` layout classes
    - _Requirements: 2.1, 2.7_

  - [x] 3.2 Create page wrapper components
    - Create `src/pages/ExplorerPage.tsx` wrapping the existing ThreePanel + FileExplorer + FileViewer + MetadataSidebar
    - Create `src/pages/GraphPage.tsx` wrapping KnowledgeGraph
    - Create `src/pages/SearchPage.tsx` wrapping SearchResults
    - Create `src/pages/PlaygroundPage.tsx` as a placeholder for the Chat Playground
    - Move existing App.tsx state logic into ExplorerPage
    - _Requirements: 2.2, 2.3, 2.4, 2.5_

  - [x] 3.3 Rewrite App.tsx with router configuration
    - Replace current App component with `createBrowserRouter` + `RouterProvider`
    - Define routes: index → ExplorerPage, /graph → GraphPage, /playground → PlaygroundPage, /search → SearchPage
    - Add catch-all route with `<Navigate to="/" replace />`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x]* 3.4 Write property test for undefined route redirect
    - **Property 2: Undefined routes redirect to root**
    - **Validates: Requirements 2.6**

- [x] 4. Checkpoint - Verify routing works and all existing views are accessible
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Chat Playground — API client and types
  - [x] 5.1 Add chat-related TypeScript types
    - Add `ChatMessage`, `SourceAttribution`, `RetrievalMetadata`, `TokenUsage` interfaces to `src/types/index.ts`
    - Add `ChatRequest`, `ChatResponse`, `SSEEvent`, `ChatConfig` types
    - _Requirements: 3.1, 4.1, 4.2, 4.3, 5.1, 9.1, 9.2_

  - [x] 5.2 Add chat API functions to client.ts
    - Export `sendChatMessage` function (POST /api/chat)
    - Export `streamChatMessage` async generator function (POST /api/chat/stream with SSE parsing)
    - Implement SSE line parsing with event/data extraction
    - Apply existing camelCase↔snake_case transformations to chat payloads
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x]* 5.3 Write property test for chat request parameter inclusion
    - **Property 3: Chat request includes all configured parameters**
    - **Validates: Requirements 3.3, 5.3**

  - [x]* 5.4 Write property test for case transformation round-trip
    - **Property 12: Case transformation round-trip**
    - **Validates: Requirements 9.3, 9.4**

- [x] 6. Implement Chat Playground — useChat hook and streaming
  - [x] 6.1 Create useChat hook with state management
    - Create `src/hooks/useChat.ts`
    - Implement message state (ChatMessage[]), streaming flag, config state
    - Generate session_id via `crypto.randomUUID()` on hook mount
    - Implement `sendMessage` that adds user message immediately, creates placeholder assistant message, and initiates stream
    - _Requirements: 3.1, 3.3, 3.4, 3.5, 3.6_

  - [x] 6.2 Implement SSE event handling in useChat
    - Handle "token" events by appending content to assistant message
    - Handle "sources" events by attaching source attributions
    - Handle "metadata" events by storing retrieval metadata
    - Handle "done" events by marking message complete and re-enabling input
    - Handle "error" events by displaying error inline and re-enabling input
    - Implement AbortController for cancellation on unmount/navigation
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x]* 6.3 Write property test for session ID uniqueness
    - **Property 4: Session ID uniqueness and format validity**
    - **Validates: Requirements 3.4**

  - [x]* 6.4 Write property test for token accumulation
    - **Property 6: Token accumulation produces correct message**
    - **Validates: Requirements 4.1**

  - [x]* 6.5 Write property test for metadata storage preservation
    - **Property 8: Metadata storage preservation**
    - **Validates: Requirements 4.3**

- [x] 7. Implement Chat Playground — UI components
  - [x] 7.1 Create MessageList and MessageBubble components
    - Create `src/components/Chat/MessageList.tsx` with shadcn ScrollArea
    - Create `src/components/Chat/MessageBubble.tsx` with role-based styling (user vs assistant)
    - Implement auto-scroll to latest message on new content
    - Use shadcn Card for message containers
    - _Requirements: 3.1, 3.7, 7.7, 7.8_

  - [x] 7.2 Create ChatInput component
    - Create `src/components/Chat/ChatInput.tsx` with shadcn Textarea and Button
    - Implement submit on Enter (Shift+Enter for newline)
    - Disable submit button while streaming is in progress
    - _Requirements: 3.2, 3.6_

  - [x] 7.3 Create ChatConfig component
    - Create `src/components/Chat/ChatConfig.tsx`
    - Add retrieval mode selector (local/global/combined) using shadcn Select, default to "combined"
    - Add optional top_k input with validation (1–50)
    - Add optional max_tokens input with validation (1000–16000)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 7.4 Create SourceAttribution component
    - Create `src/components/Chat/SourceAttribution.tsx`
    - Render each source as a clickable shadcn Badge showing fileName, department, chunkIndex
    - On click, navigate to `/?fileId={fileId}` to open file in explorer
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 7.5 Create ChatPlayground page component and wire everything together
    - Create `src/components/Chat/ChatPlayground.tsx` composing MessageList, ChatInput, ChatConfig, SourceAttribution
    - Update `src/pages/PlaygroundPage.tsx` to render ChatPlayground
    - Wire useChat hook to all child components
    - _Requirements: 3.1, 3.2, 4.1, 4.4, 5.1_

  - [x]* 7.6 Write property test for user message immediate display
    - **Property 5: User message immediate display**
    - **Validates: Requirements 3.5**

  - [x]* 7.7 Write property test for numeric parameter validation
    - **Property 10: Numeric parameter validation**
    - **Validates: Requirements 5.4, 5.5**

  - [x]* 7.8 Write property test for source attribution rendering
    - **Property 7: Source attribution rendering completeness**
    - **Validates: Requirements 4.2, 6.2**

  - [x]* 7.9 Write property test for source attribution navigation
    - **Property 11: Source attribution navigation**
    - **Validates: Requirements 6.1**

  - [x]* 7.10 Write property test for error event inline display
    - **Property 9: Error event inline display**
    - **Validates: Requirements 4.5**

- [x] 8. Checkpoint - Verify Chat Playground streams and displays messages correctly
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Migrate existing components to shadcn/ui
  - [x] 9.1 Migrate TopNav to shadcn NavigationMenu
    - Replace custom nav links with shadcn NavigationMenu component
    - Replace custom buttons with shadcn Button
    - Replace custom dropdowns with shadcn DropdownMenu
    - Integrate with react-router-dom `<Link>` / `useNavigate` for route switching
    - _Requirements: 2.7, 7.1_

  - [x] 9.2 Migrate ThreePanel layout to shadcn ScrollArea
    - Replace custom scrollable panels with shadcn ScrollArea
    - Implement collapsible side panels for screens < 1024px
    - Add shadcn Sheet for mobile viewport (< 768px) side panel access
    - _Requirements: 7.8, 10.1, 10.3_

  - [x] 9.3 Migrate FileExplorer to shadcn components
    - Replace custom inputs with shadcn Input
    - Replace custom buttons with shadcn Button
    - Wrap file list in shadcn ScrollArea
    - _Requirements: 7.2, 7.8_

  - [x] 9.4 Migrate MetadataSidebar to shadcn components
    - Replace custom containers with shadcn Card
    - Replace tag elements with shadcn Badge
    - Replace custom inputs with shadcn Input
    - _Requirements: 7.2, 7.7_

  - [x] 9.5 Migrate SearchResults to shadcn components
    - Replace custom result cards with shadcn Card
    - Replace loading indicators with shadcn Skeleton
    - _Requirements: 7.5, 7.7_

  - [x] 9.6 Migrate FileViewer to shadcn components
    - Wrap viewer content in shadcn Card
    - Add shadcn ScrollArea for document scrolling
    - _Requirements: 7.7, 7.8_

  - [x] 9.7 Migrate dialogs and modals to shadcn Dialog
    - Replace any custom modal patterns with shadcn Dialog
    - Replace custom select/dropdown patterns with shadcn Select or DropdownMenu
    - _Requirements: 7.3, 7.4_

- [x] 10. Implement responsive layout adaptations
  - [x] 10.1 Add responsive breakpoint behavior
    - Implement collapsible side panels at 768–1023px with toggle buttons
    - Implement shadcn Sheet drawer for side panels below 768px
    - Ensure Chat Playground renders as single-column at all widths
    - _Requirements: 10.1, 10.2, 10.3_

- [x] 11. Final checkpoint - Full build verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each phase
- Property tests validate universal correctness properties from the design document
- The migration maintains identical user-facing functionality throughout (Requirement 7.6)
- TypeScript is the implementation language (React 19 + Vite 8 + Tailwind CSS 4)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "1.4"] },
    { "id": 3, "tasks": ["3.1", "3.2"] },
    { "id": 4, "tasks": ["3.3", "3.4"] },
    { "id": 5, "tasks": ["5.1"] },
    { "id": 6, "tasks": ["5.2", "5.3", "5.4"] },
    { "id": 7, "tasks": ["6.1"] },
    { "id": 8, "tasks": ["6.2", "6.3"] },
    { "id": 9, "tasks": ["6.4", "6.5", "7.1", "7.2", "7.3", "7.4"] },
    { "id": 10, "tasks": ["7.5", "7.6", "7.7", "7.8", "7.9", "7.10"] },
    { "id": 11, "tasks": ["9.1"] },
    { "id": 12, "tasks": ["9.2", "9.3", "9.4", "9.5", "9.6", "9.7"] },
    { "id": 13, "tasks": ["10.1"] }
  ]
}
```
