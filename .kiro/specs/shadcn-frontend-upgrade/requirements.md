# Requirements Document

## Introduction

This feature upgrades the Executive Copilot frontend to use shadcn/ui components incrementally, introduces client-side routing via react-router-dom, adds a dedicated Chat Playground page with real-time SSE streaming, and wires up all backend API endpoints that are not yet consumed in the UI.

## Glossary

- **App**: The top-level React application shell that provides routing and layout
- **Router**: The react-router-dom routing layer that maps URL paths to page components
- **Chat_Playground**: A dedicated page where users interact with the LLM chat endpoints
- **Chat_Stream_Handler**: The client-side module responsible for consuming SSE events from POST /api/chat/stream
- **Message_List**: The scrollable container displaying the conversation history of user and assistant messages
- **Token_Renderer**: The component that progressively renders streamed tokens into the assistant message bubble
- **Source_Attribution_Panel**: The UI section that displays source file references returned by the chat API
- **shadcn_Component**: A UI primitive from the shadcn/ui library installed and configured for the project
- **Existing_Component**: A current custom Tailwind component (FileExplorer, FileViewer, TopNav, ThreePanel, MetadataSidebar, SearchResults, KnowledgeGraph)
- **Dark_Theme**: The application-wide dark color scheme using CSS variables compatible with shadcn/ui theming

## Requirements

### Requirement 1: shadcn/ui Installation and Configuration

**User Story:** As a developer, I want shadcn/ui installed and configured in the project, so that I can use its component primitives throughout the application.

#### Acceptance Criteria

1. THE App SHALL have shadcn/ui initialized with Tailwind CSS 4 and the "new-york" style variant configured
2. THE App SHALL use CSS variables for theming that map to the existing dark surface-100/200/300 palette
3. THE App SHALL include a `cn()` utility function that merges Tailwind classes using clsx and tailwind-merge

### Requirement 2: Client-Side Routing

**User Story:** As a user, I want distinct URL paths for different views, so that I can navigate directly to the file explorer, knowledge graph, or chat playground via the browser address bar.

#### Acceptance Criteria

1. THE Router SHALL define a root layout route that renders the top navigation and an outlet for child pages
2. THE Router SHALL map the path "/" to the existing three-panel file explorer view
3. THE Router SHALL map the path "/graph" to the knowledge graph view
4. THE Router SHALL map the path "/playground" to the Chat_Playground page
5. THE Router SHALL map the path "/search" to the search results view
6. WHEN a user navigates to an undefined path, THE Router SHALL redirect to "/"
7. THE App SHALL use shadcn_Component navigation elements (e.g., NavigationMenu or Tabs) in the top navigation bar to switch between routes

### Requirement 3: Chat Playground — Message Interface

**User Story:** As a user, I want a chat interface on the Playground page, so that I can ask questions about my knowledge base and receive AI-generated answers.

#### Acceptance Criteria

1. THE Chat_Playground SHALL display a Message_List showing the full conversation history for the current session
2. THE Chat_Playground SHALL provide a text input area with a submit button for composing new queries
3. WHEN the user submits a query, THE Chat_Playground SHALL send the request to POST /api/chat/stream with the current session_id
4. THE Chat_Playground SHALL generate and persist a session_id per browser tab to support multi-turn conversations
5. WHEN the user submits a query, THE Chat_Playground SHALL display the user message immediately in the Message_List
6. THE Chat_Playground SHALL disable the submit button while a streaming response is in progress
7. THE Chat_Playground SHALL auto-scroll the Message_List to the latest message when new content arrives

### Requirement 4: Chat Playground — SSE Streaming

**User Story:** As a user, I want to see the AI response appear token-by-token in real time, so that I get immediate feedback without waiting for the full response.

#### Acceptance Criteria

1. WHEN the Chat_Stream_Handler receives a "token" SSE event, THE Token_Renderer SHALL append the token content to the current assistant message in the Message_List
2. WHEN the Chat_Stream_Handler receives a "sources" SSE event, THE Source_Attribution_Panel SHALL display the list of source file attributions below the assistant message
3. WHEN the Chat_Stream_Handler receives a "metadata" SSE event, THE Chat_Playground SHALL store the retrieval metadata (retrieval_mode, documents_retrieved, token_usage) for display
4. WHEN the Chat_Stream_Handler receives a "done" SSE event, THE Chat_Playground SHALL re-enable the submit button and mark the assistant message as complete
5. IF the Chat_Stream_Handler receives an "error" SSE event, THEN THE Chat_Playground SHALL display the error message inline and re-enable the submit button
6. IF the SSE connection drops unexpectedly, THEN THE Chat_Playground SHALL display a connection error notification and re-enable the submit button

### Requirement 5: Chat Playground — Configuration Controls

**User Story:** As a user, I want to configure retrieval parameters for my chat queries, so that I can control how the AI searches the knowledge base.

#### Acceptance Criteria

1. THE Chat_Playground SHALL provide a retrieval mode selector with options: "local", "global", "combined"
2. THE Chat_Playground SHALL default the retrieval mode to "combined"
3. WHERE the user selects a retrieval mode, THE Chat_Playground SHALL include the selected mode in subsequent chat requests as the retrieval_mode field
4. THE Chat_Playground SHALL provide an optional top_k input that accepts values between 1 and 50
5. THE Chat_Playground SHALL provide an optional max_tokens input that accepts values between 1000 and 16000

### Requirement 6: Source Attribution Interaction

**User Story:** As a user, I want to click on source attributions to navigate to the referenced file, so that I can verify the AI's answer against the original document.

#### Acceptance Criteria

1. WHEN the user clicks a source attribution item, THE App SHALL navigate to the file explorer view with the referenced file selected and displayed in the FileViewer
2. THE Source_Attribution_Panel SHALL display the file name, department, and chunk index for each source
3. THE Source_Attribution_Panel SHALL render each source as a clickable element styled with shadcn_Component (e.g., Badge or Button variant)

### Requirement 7: Incremental shadcn/ui Component Migration

**User Story:** As a developer, I want to replace custom Tailwind components with shadcn/ui equivalents one at a time, so that the application remains functional throughout the migration.

#### Acceptance Criteria

1. THE App SHALL replace the custom top navigation bar with shadcn_Component equivalents (NavigationMenu, Button, DropdownMenu)
2. THE App SHALL replace custom input fields and buttons across all views with shadcn_Component Input, Button, and Textarea primitives
3. THE App SHALL replace custom modal/dialog patterns with shadcn_Component Dialog
4. THE App SHALL replace custom dropdown menus with shadcn_Component DropdownMenu or Select
5. THE App SHALL replace custom loading indicators with shadcn_Component Skeleton or Spinner patterns
6. WHILE an Existing_Component is being migrated, THE App SHALL maintain identical user-facing functionality
7. THE App SHALL use shadcn_Component Card for content containers (file metadata, search results, chat messages)
8. THE App SHALL use shadcn_Component ScrollArea for scrollable panels (file list, message list, metadata sidebar)

### Requirement 8: Dark Theme Consistency

**User Story:** As a user, I want the application to maintain a consistent dark theme after the shadcn/ui migration, so that the visual experience remains cohesive.

#### Acceptance Criteria

1. THE App SHALL configure shadcn/ui CSS variables to produce a dark theme as the default appearance
2. THE App SHALL map the existing surface-100/200/300 color palette to the shadcn/ui background, card, and muted CSS variable slots
3. THE App SHALL ensure text contrast ratios meet WCAG 2.1 AA standards (minimum 4.5:1 for normal text)
4. THE App SHALL apply consistent border-radius, spacing, and shadow values from the shadcn/ui theme tokens across all components

### Requirement 9: Chat API Client Integration

**User Story:** As a developer, I want the chat API endpoints added to the frontend API client module, so that the Chat Playground can communicate with the backend.

#### Acceptance Criteria

1. THE App SHALL export a `sendChatMessage` function in the API client that posts to POST /api/chat and returns the structured response
2. THE App SHALL export a `streamChatMessage` function in the API client that opens an SSE connection to POST /api/chat/stream and returns an event source or async iterator
3. THE App SHALL apply the existing snake_case-to-camelCase response transformation to chat API responses
4. THE App SHALL apply the existing camelCase-to-snake_case request transformation to chat API request bodies

### Requirement 10: Responsive Layout

**User Story:** As a user, I want the application layout to adapt to different screen sizes, so that I can use the tool on various devices.

#### Acceptance Criteria

1. THE App SHALL render the three-panel layout with collapsible side panels on screens narrower than 1024px
2. THE Chat_Playground SHALL render as a single-column layout that fills the available viewport width
3. THE App SHALL use shadcn_Component Sheet or Drawer for side panel content on mobile viewports (below 768px)
