# Implementation Tasks

## Task 1: Dashboard Analytics Backend
- [x] 1.1 Create `backend/app/models/file_relationship.py` with FileRelationship SQLAlchemy model (id, source_file_id, target_file_id, relationship_type, confidence, created_at)
- [x] 1.2 Create `backend/app/schemas/dashboard.py` with Pydantic response models (DashboardAnalytics, KPIData, DeptDistribution, QueryTrend, RecentActivity)
- [x] 1.3 Create `backend/app/services/dashboard_service.py` with aggregation queries: total docs from files table, daily queries from chat_messages, department distribution from chat_messages grouped by session metadata, 7-day trend, recent activities (last 10 uploads + queries)
- [x] 1.4 Create `backend/app/routers/dashboard.py` with GET /api/dashboard/analytics endpoint that calls DashboardService and returns DashboardAnalytics response
- [x] 1.5 Register dashboard router in `backend/app/main.py` with `/api` prefix

## Task 2: Dashboard Frontend Integration
- [x] 2.1 Create `frontend/src/api/dashboard.ts` with `getDashboardAnalytics()` function calling GET /api/dashboard/analytics
- [x] 2.2 Create `frontend/src/hooks/useDashboard.ts` hook that fetches analytics on mount, handles loading/error states, and caches last successful response
- [x] 2.3 Modify `frontend/src/app/components/DashboardPage.tsx`: remove all hardcoded data arrays (salesData, queryTrend, deptActivity, RECENT_ACTIVITIES), replace with useDashboard hook data
- [x] 2.4 Replace "Penjualan vs Target" BarChart with "Request/Query per Department" BarChart using department distribution data from API
- [x] 2.5 Add loading skeleton components for KPI cards and charts during data fetch
- [x] 2.6 Add error fallback: display cached data with stale warning when API fails

## Task 3: Copilot Chat Visualization Transform
- [x] 3.1 Create `frontend/src/utils/visualizationDetector.ts` with functions: detectMarkdownTable(text), detectNumericData(text), detectList(text) that return structured parsed data or null
- [x] 3.2 Create `frontend/src/app/components/chatplayground/VisualizationTransform.tsx` component that renders detected tables as HTML tables, numeric data as Recharts charts (bar/line/pie toggle), and lists as styled components
- [x] 3.3 Integrate VisualizationTransform into ChatPage message rendering: wrap assistant messages, add "Text/Visual" toggle button per message
- [x] 3.4 Ensure plain text messages (no detected patterns) render as standard markdown without transformation

## Task 4: Copilot Chat Auto-Save and Pagination
- [x] 4.1 Modify ChatPage to auto-create session via POST /api/sessions when user sends first message in a new conversation (derive title from first 50 chars of message)
- [x] 4.2 After session creation, auto-persist each subsequent message to backend using existing sessions API
- [x] 4.3 Add retry logic (3 attempts, exponential backoff) for session save failures with non-blocking toast on final failure
- [x] 4.4 Add pagination support to backend GET /api/sessions endpoint: accept `page` and `page_size` query params, return total count in response
- [x] 4.5 Modify `frontend/src/app/components/SessionList.tsx` to load first page (page_size=20), add "Load More" button that fetches next page and appends results
- [x] 4.6 Display total session count in session list header

## Task 5: Search Page Fix
- [x] 5.1 Read and fix `frontend/src/app/components/search/SearchResults.tsx`: ensure it calls POST /api/search/combined with correct request body schema (query, max_tokens, top_k, num_communities)
- [x] 5.2 Map SearchResponse fields (chunks, source_attributions, metadata) to display: file name, relevance score, text snippet, department
- [x] 5.3 Add department filter dropdown and minimum score slider to SearchResults
- [x] 5.4 Add error state with retry button and empty state with suggestions
- [x] 5.5 Group results by source file with collapsible sections and highlight matching text

## Task 6: Knowledge Base Grouping and Icons
- [x] 6.1 Create `frontend/src/utils/fileIcons.ts` with a mapping function: extension → {icon component, color}. Cover pdf, xlsx, xls, csv, docx, txt, md, json, png, jpg, tiff with distinct icons. Default to generic File icon for unknown extensions.
- [x] 6.2 Add "View Mode" toggle to KnowledgeBasePage: "Flat List" (current) and "Grouped" with sub-options "By File Type" and "By Department"
- [x] 6.3 Implement groupBy file type rendering: collapsible sections per type (PDF, XLSX, CSV, DOCX, TXT, Other) with count badges
- [x] 6.4 Implement groupBy department rendering: collapsible sections per department with count badges
- [x] 6.5 Replace hardcoded TYPE_ICONS/TYPE_COLORS in KnowledgeBasePage with the new fileIcons utility

## Task 7: File Explorer AI Suggestions
- [x] 7.1 Create `backend/app/services/ai_suggestion_service.py` with methods: `suggest_tags(file_id, db)` and `suggest_rename(file_id, db)` that use LangChain LLM to analyze extracted_text and return suggestions
- [x] 7.2 Add POST /api/files/{file_id}/suggest-tags endpoint to files router: calls ai_suggestion_service.suggest_tags, returns list of up to 5 tag strings
- [x] 7.3 Add POST /api/files/{file_id}/suggest-rename endpoint to files router: calls ai_suggestion_service.suggest_rename, returns list of up to 3 suggested file names following [department]_[topic]_[date].[ext] pattern
- [x] 7.4 Modify `frontend/src/app/components/explorer/MetadataSidebar.tsx`: add "Suggest Tags" button that calls the suggest-tags endpoint and displays results as clickable chips (accept/dismiss)
- [x] 7.5 Add "Suggest Rename" button to MetadataSidebar: call suggest-rename endpoint, display options, on select call PATCH /api/files/{id} to rename
- [x] 7.6 Add PATCH /api/files/{file_id} endpoint to files router to support renaming a file (update name field)

## Task 8: Knowledge Graph Backend
- [x] 8.1 Create `backend/app/schemas/graph.py` with Pydantic models: GraphNode (id, label, type, position:{x,y}, data:{}), GraphEdge (id, source, target, label, type), GraphData (nodes, edges), CreateRelationshipRequest, AutoReferenceResponse
- [x] 8.2 Create `backend/app/services/graph_service.py` with methods: `get_graph_data(db)` (builds nodes from files, edges from file_relationships, computes force-directed positions), `create_relationship(source_id, target_id, type, db)`, `delete_relationship(id, db)`, `auto_reference(db, embedding_model)` (find similar files via embedding cosine similarity > 0.7, exclude existing relationships)
- [x] 8.3 Create `backend/app/routers/graph.py` with endpoints: GET /api/graph, POST /api/graph/relationships, DELETE /api/graph/relationships/{id}, POST /api/graph/auto-reference
- [x] 8.4 Register graph router in `backend/app/main.py` with `/api` prefix
- [x] 8.5 Add auto-register of FileRelationship model in main.py imports so table is created at startup
- [x] 8.6 Modify `frontend/src/app/components/graph/KnowledgeGraph.tsx`: add "Auto-Reference" button that calls POST /api/graph/auto-reference and displays suggested edges as dashed/animated lines with accept/dismiss controls

## Task 9: Ingestion Page Fix
- [x] 9.1 Read and fix `frontend/src/app/components/ingestion/FileUpload.tsx`: ensure department field is populated from GET /api/departments (not hardcoded empty string), add department dropdown selector
- [x] 9.2 Ensure upload form sends FormData with correct field names (file, department, subfolder) to POST /api/ingestion/upload
- [x] 9.3 Add proper error handling for 413 (file too large) and 422 (missing metadata) responses with user-friendly messages
- [x] 9.4 Verify the jobs tab properly maps IngestionJob response fields to the JobCard display (confirm field name alignment between frontend types and backend schema)

## Task 10: User Management Backend
- [x] 10.1 Create `backend/app/models/user.py` with User SQLAlchemy model (id, name, email unique, role, department, status, password_hash, phone, bio, avatar, last_login_at, created_at, updated_at)
- [x] 10.2 Create `backend/app/schemas/user.py` with Pydantic models: UserCreate (name, email, role, department, password), UserUpdate (all optional), UserResponse (excludes password_hash), UserListResponse (items + total)
- [x] 10.3 Create `backend/app/services/user_service.py` with CRUD logic: create (hash password with bcrypt, check email uniqueness), list (filter by role/dept/status, text search), update, soft-delete
- [x] 10.4 Create `backend/app/routers/users.py` with endpoints: GET /api/users (list+filter), POST /api/users (create), PATCH /api/users/{id} (update), DELETE /api/users/{id} (soft-delete)
- [x] 10.5 Register users router in `backend/app/main.py` with `/api` prefix
- [x] 10.6 Add bcrypt to backend dependencies (requirements.txt or pyproject.toml)

## Task 11: User Management Frontend Integration
- [x] 11.1 Create `frontend/src/api/users.ts` with functions: getUsers(filters), createUser(data), updateUser(id, data), deleteUser(id)
- [x] 11.2 Create `frontend/src/hooks/useUsers.ts` hook with CRUD operations, loading states, and error handling
- [x] 11.3 Modify `frontend/src/app/components/AdminUsersPage.tsx`: remove INITIAL_USERS, fetch from API on mount via useUsers hook
- [x] 11.4 Connect handleSave to createUser/updateUser API, handleDelete to deleteUser API, toggleStatus to updateUser API
- [x] 11.5 Add error toast notifications for failed API operations

## Task 12: Settings Backend
- [x] 12.1 Create `backend/app/models/user_settings.py` with UserSettings SQLAlchemy model (id, user_id unique+indexed, profile_json, notifications_json, chatbot_json, security_json, created_at, updated_at)
- [x] 12.2 Create `backend/app/schemas/settings.py` with Pydantic models: ProfileSettings, NotificationSettings, ChatbotSettings, SecuritySettings, SettingsResponse, SettingsUpdate
- [x] 12.3 Create `backend/app/routers/settings.py` with endpoints: GET /api/settings/{user_id} (return stored or defaults), PUT /api/settings/{user_id} (upsert, partial update - only overwrite provided sections)
- [x] 12.4 Register settings router in `backend/app/main.py` with `/api` prefix

## Task 13: Settings Frontend Integration
- [x] 13.1 Create `frontend/src/api/settings.ts` with functions: getSettings(userId), saveSettings(userId, data)
- [x] 13.2 Create `frontend/src/hooks/useSettings.ts` hook that loads settings on mount and provides save function
- [x] 13.3 Modify `frontend/src/app/components/SettingsPage.tsx`: load initial state from API on mount, change handleSave to call PUT /api/settings/{userId}
- [x] 13.4 Add dirty state tracking: disable "Simpan Perubahan" when no changes detected (compare current form to last-saved snapshot)
- [x] 13.5 Add error handling: display error message on save failure, keep form state for retry

## Task 14: Integration Testing and Router Registration
- [x] 14.1 Verify all new routers (dashboard, graph, users, settings) are properly registered in main.py with try/except ImportError pattern
- [x] 14.2 Verify all new models are imported in main.py so tables are created at startup
- [x] 14.3 Run backend startup to confirm all tables are created without errors
- [x] 14.4 Verify frontend can call all new endpoints through Vite proxy (check vite.config.ts proxy settings)
