# Requirements Document

## Introduction

This document defines the requirements for making all views and features in the Executive Copilot application fully functional. The application is a knowledge base management system with an AI copilot for departmental document search, analysis, and visualization. Currently, several pages rely on hardcoded data, client-side-only state, or missing backend endpoints. This feature set addresses all gaps to create a production-ready system with real data persistence, functional search, knowledge graph visualization, user management, and intelligent AI-powered features.

## Glossary

- **Dashboard_Service**: The backend service responsible for aggregating analytics data (document counts, query statistics, department activity) from the database and returning real-time metrics.
- **Copilot_Chat**: The frontend chat interface component that sends user queries to the LLM backend and renders responses with optional visualization transforms.
- **Chat_Backend**: The FastAPI router and LangChain-based service that handles chat streaming, retrieval-augmented generation, and session persistence.
- **Search_UI**: The frontend search page component that provides combined local/global search over the knowledge base.
- **Search_Service**: The backend retrieval service that performs vector similarity and global search across embedded document chunks.
- **Knowledge_Base_UI**: The frontend page for browsing, filtering, and managing uploaded documents.
- **File_Explorer_UI**: The frontend document explorer with tree navigation, file preview, and metadata sidebar.
- **Graph_Service**: The backend router responsible for generating and managing knowledge graph data (nodes representing files/entities, edges representing relationships).
- **Graph_UI**: The frontend ReactFlow-based visualization component for the knowledge graph.
- **Ingestion_Service**: The backend pipeline that handles file upload, validation, preprocessing, chunking, embedding, and deduplication.
- **Ingestion_UI**: The frontend dashboard for uploading files, monitoring ingestion jobs, and configuring batch loaders.
- **User_Service**: The backend router responsible for CRUD operations on user accounts with role-based access control.
- **User_Management_UI**: The frontend admin page for managing user accounts, roles, and statuses.
- **Settings_Service**: The backend router responsible for persisting application settings (user profile, chatbot preferences, notification preferences).
- **Settings_UI**: The frontend settings page for user profile, security, notifications, and chatbot configuration.
- **AI_Suggestion_Service**: The backend service that uses LLM to generate tag suggestions and rename suggestions for files based on content analysis.
- **Department**: One of the organizational units (accounting_tax, demand_supply, finance, logistic, master) that owns documents in the knowledge base.
- **Session**: A chat conversation thread consisting of ordered messages between user and assistant, persisted in the database.
- **Visualization_Transform**: The process of detecting structured data in AI responses (tables, charts, lists) and rendering them as interactive visual components instead of plain text.

## Requirements

### Requirement 1: Dashboard Real-Time Analytics API

**User Story:** As an executive, I want the dashboard to show real data from the knowledge base, so that I can make informed decisions based on actual system activity.

#### Acceptance Criteria

1. WHEN the Dashboard_Service receives a request for analytics, THE Dashboard_Service SHALL return total document count (from the files table), total query count for the current day (messages with role "user" in chat_messages where created_at falls within the server's current calendar day in UTC), number of active departments (distinct department values in the files table that have at least one file), and AI accuracy percentage computed as the proportion of assistant messages that contain a non-empty sources array divided by total assistant messages, expressed as a percentage rounded to one decimal place.
2. WHEN the Dashboard_Service receives a request for department query distribution, THE Dashboard_Service SHALL return a breakdown of chat queries per department for the current week (Monday 00:00 UTC through current time), where department is derived from the department field of files referenced in the chat_messages sources array, and each entry includes the department name and query count.
3. WHEN the Dashboard_Service receives a request for recent activity, THE Dashboard_Service SHALL return the 10 most recent activities (uploads from the files table and user-role messages from chat_messages) with department name, action description (file name for uploads, first 80 characters of message content for queries), activity type ("upload" or "query"), and a UTC ISO-8601 timestamp, ordered by most recent first.
4. WHEN the Dashboard_Service receives a request for query trend data, THE Dashboard_Service SHALL return daily query counts for the last 7 calendar days (UTC) computed from user-role messages in the chat_messages table, with each entry containing the date (YYYY-MM-DD) and the count of queries for that day, including days with zero queries.
5. THE Dashboard_Service SHALL expose a single GET endpoint at /api/dashboard/analytics that returns all KPI metrics, department distribution, query trend, and recent activities in one response within 2 seconds.
6. IF the Dashboard_Service encounters a database error while computing analytics, THEN THE Dashboard_Service SHALL return an error response with a message indicating the analytics could not be computed, without exposing internal error details.
7. IF the chat_messages table or files table contains no records, THEN THE Dashboard_Service SHALL return zero for all count metrics, an empty list for department distribution and recent activities, and 0.0 for AI accuracy percentage.

### Requirement 2: Dashboard Frontend Integration

**User Story:** As an executive, I want the dashboard UI to display live data instead of hardcoded values, so that the information is always current.

#### Acceptance Criteria

1. WHEN the DashboardPage loads, THE Dashboard_UI SHALL fetch analytics from /api/dashboard/analytics within 10 seconds and display real KPI values for document count, daily queries, active departments, and AI accuracy in the corresponding KPI card positions.
2. WHEN the DashboardPage loads successfully with analytics data, THE Dashboard_UI SHALL render a "Request/Query per Department" bar chart (replacing the "Penjualan vs Target" chart) showing the number of queries per department for the current calendar week (Monday through Sunday), with department names on the X-axis and query counts on the Y-axis.
3. WHILE analytics data is being fetched, THE Dashboard_UI SHALL display a loading skeleton in place of KPI cards and charts until the response is received or the 10-second timeout is reached.
4. IF the analytics API returns an error and cached data from a previous successful fetch exists, THEN THE Dashboard_UI SHALL display the cached values with a visible warning indicator stating that the displayed data may be stale.
5. IF the analytics API returns an error and no cached data exists, THEN THE Dashboard_UI SHALL display zeroes for all KPI values and empty charts with an error message indicating data is unavailable and a retry button.
6. IF the user role is "staff", THEN THE Dashboard_UI SHALL filter all analytics displays (KPI cards, charts, and activity list) to show only data belonging to the staff member's own department.

### Requirement 3: Copilot Chat Visualization Transform

**User Story:** As a user, I want AI responses to be rendered as visual components (tables, charts) when the data is structured, so that I can quickly understand quantitative information.

#### Acceptance Criteria

1. WHEN the Chat_Backend returns a response containing a markdown table (detected by the presence of a header row, a separator row of dashes and pipes, and at least one data row), THE Copilot_Chat SHALL detect the table structure and render it as an interactive HTML table component with sortable columns, supporting tables of up to 100 rows and 20 columns.
2. WHEN the Chat_Backend returns a response containing numeric data with labels (detected as two or more label-value pairs where labels are text strings and values are numeric, presented in a markdown table, a key-value list, or a repeated "label: number" pattern), THE Copilot_Chat SHALL display the data as a bar chart by default using Recharts and offer a toggle to switch between bar chart, line chart, and pie chart views, supporting up to 50 data points.
3. WHEN the Chat_Backend returns a response containing a bulleted or numbered list (detected by markdown list syntax: lines starting with "- ", "* ", or "1. " patterns), THE Copilot_Chat SHALL render the list with hierarchical indentation up to 4 nesting levels and styling visually distinct from plain paragraph text.
4. WHEN a response contains a detected structured data pattern, THE Copilot_Chat SHALL display the "Visual" view by default, preserve the original text response, and provide a toggle allowing the user to switch between "Text" and "Visual" views.
5. IF the response content does not match any structured data pattern (markdown table, numeric label-value pairs, or markdown list), THEN THE Copilot_Chat SHALL render the response as standard markdown text without transformation.
6. IF the Copilot_Chat fails to render a visualization due to malformed data or a rendering error, THEN THE Copilot_Chat SHALL fall back to displaying the original text response and show a non-blocking warning indicator that the visual view is unavailable for that response.

### Requirement 4: Copilot Chat Auto-Save and Session Persistence

**User Story:** As a user, I want my chat sessions to be automatically saved after the first prompt, so that I never lose conversation context.

#### Acceptance Criteria

1. WHEN the user sends the first message in a new chat session, THE Copilot_Chat SHALL automatically create a new session via POST /api/sessions with a title set to the first 50 characters of the message content (or the full message if shorter than 50 characters), trimmed of leading and trailing whitespace.
2. WHEN a session has been auto-created, THE Copilot_Chat SHALL persist each subsequent message (user and assistant) to the backend via POST /api/sessions/{session_id}/messages in chronological order without requiring manual save, and SHALL retain unsent messages in a local queue until persistence is confirmed.
3. WHEN the user opens an existing session from the session list, THE Copilot_Chat SHALL load all messages from the backend and restore the conversation display including message content, sender role (user or assistant), message order, and any associated visualization transforms.
4. IF the auto-save request fails, THEN THE Copilot_Chat SHALL retry up to 3 times with exponential backoff starting at 1 second (1s, 2s, 4s) and display a non-blocking warning toast for 5 seconds if all retries fail, while preserving the unsent messages in the local queue for the next retry opportunity.
5. IF the session creation request (POST /api/sessions) fails after 3 retries, THEN THE Copilot_Chat SHALL display a non-blocking error toast indicating the session could not be saved, continue allowing the user to chat locally, and reattempt session creation on the next message send.

### Requirement 5: Copilot Chat Session History Pagination

**User Story:** As a user, I want the session history list to be paginated, so that I can efficiently browse through many past conversations.

#### Acceptance Criteria

1. THE Chat_Backend SHALL support pagination parameters (page, page_size) on the GET /api/sessions endpoint, enforce page_size between 1 and 100 (defaulting to 20), return results sorted by last activity descending, and include total count and a boolean indicating whether more pages are available.
2. WHEN the session list loads, THE Copilot_Chat SHALL request the first page (page_size=20) and display a "Load More" button when more sessions are available.
3. WHEN the user clicks "Load More", THE Copilot_Chat SHALL display a loading indicator in place of the button, fetch the next page, and append results to the displayed list within 2 seconds.
4. THE Copilot_Chat SHALL display the total session count in the session list header.
5. IF the pagination request fails or the Chat_Backend receives an invalid page or page_size parameter (non-integer, zero, negative, or exceeding bounds), THEN THE Chat_Backend SHALL return an error response indicating the validation failure, and THE Copilot_Chat SHALL display an error message with a retry option while preserving previously loaded sessions.
6. WHEN the total session count is zero, THE Copilot_Chat SHALL display an empty state message indicating no past conversations exist.

### Requirement 6: Search Page Functionality

**User Story:** As a user, I want the search page to work correctly with the existing backend search endpoints, so that I can find documents across the knowledge base.

#### Acceptance Criteria

1. WHEN the user enters a search query and submits, THE Search_UI SHALL send a POST request to /api/search/combined with the query text and display the results.
2. THE Search_UI SHALL display search results with source file name, relevance score, matched text snippet, and department origin.
3. WHEN search results are returned, THE Search_UI SHALL group results by source file and highlight matching text within snippets.
4. THE Search_UI SHALL provide filter controls to narrow results by department and minimum relevance score.
5. IF the search request fails or returns an error, THEN THE Search_UI SHALL display a descriptive error message with a retry button.
6. WHEN no results are found for a query, THE Search_UI SHALL display an empty state with suggestions (e.g., "Try broader keywords" or "Check spelling").

### Requirement 7: Knowledge Base Grouping and File Type Icons

**User Story:** As a user, I want the knowledge base to group files by type or department, and show file-type icons, so that I can quickly find and identify documents.

#### Acceptance Criteria

1. THE Knowledge_Base_UI SHALL provide a toggle to switch between "Flat List" view and "Grouped" view, with "Flat List" as the default view on initial load.
2. WHEN "Grouped" view is active, THE Knowledge_Base_UI SHALL display a grouping mode selector allowing the user to choose between "By File Type" and "By Department" grouping, with "By File Type" as the default grouping mode.
3. WHILE "Grouped" view is active with "By File Type" mode selected, THE Knowledge_Base_UI SHALL group documents into collapsible sections by file type (PDF, XLSX, CSV, DOCX, TXT, Other) with each section header showing the document count for that group, and all sections expanded by default.
4. WHILE "Grouped" view is active with "By Department" mode selected, THE Knowledge_Base_UI SHALL group documents into collapsible sections by department source, with each section header showing the department name and document count, and all sections expanded by default.
5. THE Knowledge_Base_UI SHALL display a distinct icon for each file extension: PDF (red document icon), XLSX/XLS (green spreadsheet icon), CSV (green table icon), DOCX (blue document icon), TXT (gray text icon), PNG/JPG (purple image icon), and a generic gray file icon for unrecognized or missing extensions.
6. IF a group contains zero documents, THEN THE Knowledge_Base_UI SHALL hide that group section from the grouped view.

### Requirement 8: File Explorer AI Tagging Suggestions

**User Story:** As a user, I want the file explorer to suggest AI-generated tags for my documents, so that I can efficiently organize files without manual effort.

#### Acceptance Criteria

1. THE AI_Suggestion_Service SHALL expose a POST endpoint at /api/files/{file_id}/suggest-tags that analyzes the file content and returns up to 5 suggested tags, where each tag is between 2 and 50 characters in length and contains only alphanumeric characters, hyphens, and underscores.
2. WHEN the user selects a file in the File_Explorer_UI and opens the metadata sidebar, THE File_Explorer_UI SHALL display a "Suggest Tags" button.
3. WHEN the user clicks "Suggest Tags", THE File_Explorer_UI SHALL display a loading indicator, call the suggestion endpoint, and upon receiving the response display returned tags as clickable chips that the user can accept or dismiss individually.
4. WHEN the user accepts a suggested tag, THE File_Explorer_UI SHALL add the tag to the file by calling PATCH /api/files/{file_id}/tags with the updated tag list and remove the accepted tag from the suggestions display.
5. IF the AI_Suggestion_Service cannot generate suggestions (LLM unavailable or file has no extracted text), THEN THE AI_Suggestion_Service SHALL return an empty list with a reason field indicating the cause of failure.
6. IF the suggestion endpoint returns an empty tag list, THEN THE File_Explorer_UI SHALL display an informational message showing the reason provided by the AI_Suggestion_Service instead of tag chips.
7. WHEN the user dismisses a suggested tag, THE File_Explorer_UI SHALL remove that tag chip from the displayed suggestions without persisting any change to the file's stored tags.

### Requirement 9: File Explorer AI Rename Suggestions

**User Story:** As a user, I want the file explorer to suggest a better file name based on content, so that file names are descriptive and consistent.

#### Acceptance Criteria

1. THE AI_Suggestion_Service SHALL expose a POST endpoint at /api/files/{file_id}/suggest-rename that analyzes the file content and returns up to 3 suggested file names.
2. WHEN the user selects a file in the File_Explorer_UI, THE File_Explorer_UI SHALL display a "Suggest Rename" button in the metadata sidebar.
3. WHEN the user clicks "Suggest Rename", THE File_Explorer_UI SHALL display a loading indicator, call the suggestion endpoint, and display returned names as selectable options.
4. WHEN the user selects a suggested name, THE File_Explorer_UI SHALL call a PATCH /api/files/{file_id} endpoint to rename the file and update the tree view.
5. THE AI_Suggestion_Service SHALL generate rename suggestions that follow the pattern: [department]_[topic]_[date].[extension] when the file has department, extracted_text (for topic inference), and modified_at date available; otherwise the service SHALL generate descriptive names based on available content without enforcing the pattern.
6. IF the AI_Suggestion_Service cannot generate rename suggestions (LLM unavailable or file has no extracted text), THEN THE AI_Suggestion_Service SHALL return an empty list with a reason field indicating the cause of failure, and THE File_Explorer_UI SHALL display an informational message.

### Requirement 10: Knowledge Graph Backend Router

**User Story:** As a user, I want the knowledge graph to load data from the backend, so that I can visualize document relationships.

#### Acceptance Criteria

1. THE Graph_Service SHALL expose a GET endpoint at /api/graph that returns nodes (files as nodes with id, label, type, position, and metadata containing department and file_id) and edges (relationships between files with id, source, target, label, and type).
2. THE Graph_Service SHALL compute node positions such that nodes sharing more relationships are positioned closer together in the layout.
3. THE Graph_Service SHALL expose a POST endpoint at /api/graph/relationships to create a new relationship between two files, accepting source_file_id, target_file_id, and relationship_type.
4. THE Graph_Service SHALL expose a DELETE endpoint at /api/graph/relationships/{id} to remove an existing relationship.
5. WHEN files are added or removed from the knowledge base, THE Graph_Service SHALL update graph nodes and remove any edges referencing deleted files to reflect the current file set.
6. THE Graph_Service SHALL restrict relationship_type values to the following exhaustive set: "references", "related_to", "depends_on", "supersedes", and "manual".
7. IF a POST to /api/graph/relationships references a source_file_id or target_file_id that does not exist, THEN THE Graph_Service SHALL return a 404 error indicating the referenced file was not found.
8. IF a POST to /api/graph/relationships would create a duplicate relationship between the same two files with the same type, THEN THE Graph_Service SHALL return a 409 Conflict error.
9. IF a DELETE to /api/graph/relationships/{id} references a relationship that does not exist, THEN THE Graph_Service SHALL return a 404 error.

### Requirement 11: Knowledge Graph AI Auto-Reference

**User Story:** As a user, I want the system to automatically suggest relationships between documents using AI, so that the knowledge graph is populated without manual effort.

#### Acceptance Criteria

1. THE AI_Suggestion_Service SHALL expose a POST endpoint at /api/graph/auto-reference that analyzes document embeddings and content similarity and returns a maximum of 20 suggested relationships per request, each including source_file_id, target_file_id, suggested relationship_type, and similarity score.
2. WHEN the user clicks "Auto-Reference" in the Graph_UI, THE Graph_UI SHALL call the auto-reference endpoint, display a loading indicator while the request is in progress, and upon success display suggested relationships as dashed edges that the user can accept or dismiss individually.
3. THE AI_Suggestion_Service SHALL only suggest relationships with a similarity score above 0.7 on a scale of 0.0 to 1.0.
4. WHEN the user accepts a suggested relationship, THE Graph_UI SHALL persist the relationship via POST /api/graph/relationships using the relationship_type provided by the suggestion (one of the types defined in Graph_Service: "references", "related_to", "depends_on", "supersedes").
5. THE AI_Suggestion_Service SHALL not suggest relationships where a relationship between the same source file and target file with the same relationship_type already exists in the graph.
6. IF the auto-reference endpoint returns an error or times out after 30 seconds, THEN THE Graph_UI SHALL display an error message indicating the suggestion process failed and allow the user to retry.
7. IF the auto-reference endpoint returns zero suggestions, THEN THE Graph_UI SHALL display a message indicating no new relationships were found.

### Requirement 12: Ingestion Page Full Functionality

**User Story:** As an admin, I want the ingestion dashboard to correctly upload files and display job progress, so that I can manage the document pipeline.

#### Acceptance Criteria

1. WHEN the user uploads a file via the Ingestion_UI upload tab, THE Ingestion_UI SHALL send the file with department and subfolder metadata to POST /api/ingestion/upload and display the returned job ID, file name, and initial status.
2. WHEN the Ingestion_UI jobs tab loads, THE Ingestion_UI SHALL fetch jobs from GET /api/ingestion/jobs with pagination (default page_size of 20) and allow filtering by status (queued, completed, failed, duplicate_exact) and by department.
3. WHEN an ingestion job progresses through pipeline stages, THE Ingestion_UI SHALL poll GET /api/ingestion/jobs every 5 seconds while any visible job has a non-terminal status and update the displayed stage progression (queued → validating → preprocessing → chunking → embedding → completed).
4. IF the upload request fails with a 413 error, THEN THE Ingestion_UI SHALL display an error message indicating the file exceeds the maximum allowed size of 50 MB and the upload form SHALL remain populated with the user's previous selections.
5. IF the upload request fails with a 422 error for missing department, THEN THE Ingestion_UI SHALL highlight the department field with a visible error border and display a validation message below the field stating that department selection is required.
6. THE Ingestion_UI SHALL provide a department selector dropdown populated from the actual department list (accounting_tax, demand_supply, finance, logistic, master).
7. THE Ingestion_UI SHALL restrict file uploads to the following accepted types: PDF, XLSX, XLS, DOCX, JSON, MD, TXT, and CSV. IF the user selects a file with a non-accepted extension, THEN THE Ingestion_UI SHALL display an error message listing the accepted file types without sending a request to the server.

### Requirement 13: User Management Backend

**User Story:** As an admin, I want user accounts to be persisted in the database, so that user management is not lost on page refresh.

#### Acceptance Criteria

1. THE User_Service SHALL expose CRUD endpoints at /api/users: GET (list with pagination and filtering), POST (create), PATCH /{id} (partial update — only provided fields are overwritten), DELETE /{id} (soft-delete by setting status to inactive).
2. THE User_Service SHALL store user records with fields: id, name (max 100 characters), email (max 254 characters), role (staff/executive/admin), department, status (active/inactive), password_hash, phone (max 20 characters), bio (max 500 characters), avatar, last_login_at, created_at, updated_at.
3. WHEN a new user is created via POST /api/users, THE User_Service SHALL require name, email, password, role, and department fields, hash the password using bcrypt before storing, and return the created user without the password_hash field.
4. THE User_Service SHALL support pagination on GET /api/users with page and page_size parameters (default page_size of 20, maximum page_size of 100) and return results with total count metadata.
5. THE User_Service SHALL support filtering by role, department, and status, and case-insensitive partial-match text search by name or email.
6. THE User_Service SHALL validate that email addresses are unique across all users including inactive users.
7. IF a user with the provided email already exists, THEN THE User_Service SHALL return a 409 Conflict error with a message indicating the email is already in use.
8. IF a POST or PATCH request contains missing required fields or invalid field values, THEN THE User_Service SHALL return a 422 Validation Error with a message indicating which fields failed validation.
9. IF a PATCH or DELETE request references a user id that does not exist, THEN THE User_Service SHALL return a 404 Not Found error.

### Requirement 14: User Management Frontend Integration

**User Story:** As an admin, I want the User Management page to use real backend data, so that changes persist and are visible to all admins.

#### Acceptance Criteria

1. WHEN the AdminUsersPage loads, THE User_Management_UI SHALL fetch the user list from GET /api/users and display real data instead of hardcoded INITIAL_USERS, showing a loading skeleton in place of the user table until the response is received.
2. WHEN the admin creates a new user, THE User_Management_UI SHALL call POST /api/users and add the returned user to the displayed list only after a successful response.
3. WHEN the admin edits a user, THE User_Management_UI SHALL call PATCH /api/users/{id} and update the displayed row with the response data only after a successful response.
4. WHEN the admin clicks delete on a user, THE User_Management_UI SHALL display a confirmation dialog before calling DELETE /api/users/{id}, and upon successful response SHALL remove the user from the displayed list.
5. WHEN the admin toggles user status, THE User_Management_UI SHALL call PATCH /api/users/{id} with the new status and update the displayed status indicator only after a successful response.
6. IF any user management API call fails, THEN THE User_Management_UI SHALL display an error toast containing the error message from the API response and revert the displayed list to its state before the failed operation.
7. IF the POST /api/users call fails with a 409 Conflict (duplicate email), THEN THE User_Management_UI SHALL keep the create/edit modal open and display a validation message on the email field indicating the email is already in use.
8. WHILE the User_Management_UI is waiting for any API call to complete, THE User_Management_UI SHALL disable the triggering action button to prevent duplicate submissions.

### Requirement 15: Settings Backend Persistence

**User Story:** As a user, I want my settings to persist on the server, so that preferences are maintained across devices and sessions.

#### Acceptance Criteria

1. THE Settings_Service SHALL expose endpoints at /api/settings: GET /api/settings/{user_id} (retrieve settings) and PUT /api/settings/{user_id} (save settings).
2. THE Settings_Service SHALL store settings with sections: profile (name, phone, bio, avatar_url), notifications (email, push, weekly, ai_alerts), chatbot (language, nuance, restrict_cross_dept, dept_keywords), and security (two_factor_enabled).
3. WHEN the user saves settings, THE Settings_Service SHALL validate the payload structure by verifying that: profile.name is a non-empty string of at most 100 characters, profile.bio is at most 500 characters, profile.phone is at most 20 characters, chatbot.language is one of "id" or "en", chatbot.nuance is one of "formal", "santai", "profesional", "ramah", or "tegas", and notification and security boolean fields are true or false.
4. IF the settings payload fails validation, THEN THE Settings_Service SHALL return a 422 response with an error message indicating which fields are invalid, without modifying any persisted data.
5. WHEN settings are retrieved and no record exists for the user, THE Settings_Service SHALL return default values: profile with empty strings for name, phone, bio, and avatar_url; notifications with email=true, push=false, weekly=true, ai_alerts=true; chatbot with language="id", nuance="formal", restrict_cross_dept=true, dept_keywords as an empty object; and security with two_factor_enabled=false.
6. THE Settings_Service SHALL support partial updates — only sections present in the request body are overwritten, and sections not included in the request body remain unchanged in storage.
7. IF a user attempts to access or modify settings for a user_id that does not match their authenticated identity, THEN THE Settings_Service SHALL return a 403 Forbidden response without revealing whether the target user_id exists.
8. WHEN the Settings_Service successfully persists settings, THE Settings_Service SHALL respond within 2 seconds and return the complete saved settings object including all sections.

### Requirement 16: Settings Frontend Integration

**User Story:** As a user, I want the Settings page to load and save from the backend, so that my preferences persist.

#### Acceptance Criteria

1. WHEN the SettingsPage loads, THE Settings_UI SHALL display a loading skeleton in place of form fields, fetch current settings from GET /api/settings/{user_id}, and populate all form fields with the persisted values once the response is received.
2. WHEN the user clicks "Simpan Perubahan", THE Settings_UI SHALL send the modified settings to PUT /api/settings/{user_id} and display a success confirmation message that remains visible for at least 2 seconds.
3. IF the save request fails, THEN THE Settings_UI SHALL display an error message indicating the failure reason and keep the form state unchanged so the user can retry.
4. WHEN chatbot settings are saved successfully, THE Settings_UI SHALL update the application-level chatbotSettings state so the Copilot_Chat uses the new preferences immediately without requiring a page reload.
5. THE Settings_UI SHALL disable the "Simpan Perubahan" button when no changes have been made (comparing current form state to last-saved state).
6. IF the initial GET /api/settings/{user_id} request fails, THEN THE Settings_UI SHALL display an error message indicating settings could not be loaded and provide a retry button that re-attempts the fetch.
7. WHILE the save request is in progress, THE Settings_UI SHALL disable the "Simpan Perubahan" button and display a loading indicator within the button to prevent duplicate submissions.
