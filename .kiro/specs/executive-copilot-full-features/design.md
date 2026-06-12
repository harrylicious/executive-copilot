# Design Document

## Overview

This design describes how to make all Executive Copilot features fully functional by adding missing backend endpoints, fixing broken frontend integrations, and replacing hardcoded data with live data from the database. The implementation spans 5 new backend routers (dashboard, graph, users, settings, AI suggestions), fixes to 3 existing pages (search, ingestion, chat), and enhancements to 3 UI components (knowledge base, file explorer, dashboard).

## Architecture

### System Context

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                    │
├──────┬──────┬───────┬──────┬──────┬──────┬──────┬──────┬────┤
│Dash- │Chat  │Search │KB    │Explo-│Graph │Inges-│Users │Set-│
│board │Page  │Page   │Page  │rer   │Page  │tion  │Page  │ting│
└──┬───┴──┬───┴───┬───┴──┬───┴──┬───┴──┬───┴──┬───┴──┬───┴──┬─┘
   │      │       │      │      │      │      │      │      │
   ▼      ▼       ▼      ▼      ▼      ▼      ▼      ▼      ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Backend (app/routers/)                   │
├──────┬──────┬───────┬──────┬──────┬──────┬──────┬──────┬────┤
│/api/ │/api/ │/api/  │/api/ │/api/ │/api/ │/api/ │/api/ │/api│
│dash- │chat  │search │files │files/│graph │inges-│users │/set│
│board │      │       │      │sugg  │      │tion  │      │ting│
└──┬───┴──┬───┴───┬───┴──┬───┴──┬───┴──┬───┴──┬───┴──┬───┴──┬─┘
   │      │       │      │      │      │      │      │      │
   ▼      ▼       ▼      ▼      ▼      ▼      ▼      ▼      ▼
┌─────────────────────────────────────────────────────────────┐
│   SQLAlchemy Models / SQLite (kb_manager.db)                 │
│   + TurboVec/ChromaDB (vector store)                         │
│   + LangChain LLM (AI suggestions)                           │
└─────────────────────────────────────────────────────────────┘
```

### New Database Models

#### User Model (New Table: `users`)
```python
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)  # UUID
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    role = Column(String, nullable=False)  # staff, executive, admin
    department = Column(String, nullable=False)
    status = Column(String, default="active")  # active, inactive
    password_hash = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    avatar = Column(String, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

#### UserSettings Model (New Table: `user_settings`)
```python
class UserSettings(Base):
    __tablename__ = "user_settings"
    id = Column(String, primary_key=True)  # UUID
    user_id = Column(String, nullable=False, unique=True, index=True)
    profile_json = Column(JSON, default=dict)  # {name, phone, bio, avatar_url}
    notifications_json = Column(JSON, default=dict)  # {email, push, weekly, ai_alerts}
    chatbot_json = Column(JSON, default=dict)  # {language, nuance, restrict_cross_dept, dept_keywords}
    security_json = Column(JSON, default=dict)  # {two_factor_enabled}
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

#### FileRelationship Model (New Table: `file_relationships`)
```python
class FileRelationship(Base):
    __tablename__ = "file_relationships"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_file_id = Column(Integer, nullable=False, index=True)
    target_file_id = Column(Integer, nullable=False, index=True)
    relationship_type = Column(String, nullable=False)  # references, related_to, depends_on, supersedes, manual
    confidence = Column(Float, nullable=True)  # AI-generated confidence score
    created_at = Column(DateTime, server_default=func.now())
```

### New Backend Routers

#### 1. Dashboard Router (`/api/dashboard`)
- `GET /api/dashboard/analytics` — Returns aggregated KPIs, department distribution, query trends, and recent activities.
- Queries: `files` table for document count, `chat_messages` for query counts, `chat_sessions` for department activity.

#### 2. Graph Router (`/api/graph`)
- `GET /api/graph` — Returns nodes (from `files` table) and edges (from `file_relationships` table) with computed positions.
- `POST /api/graph/relationships` — Creates a new file relationship.
- `DELETE /api/graph/relationships/{id}` — Removes a relationship.
- `POST /api/graph/auto-reference` — Uses embedding similarity to suggest relationships.

#### 3. Users Router (`/api/users`)
- `GET /api/users` — List users with filtering (role, department, status, search).
- `POST /api/users` — Create user with bcrypt password hashing.
- `PATCH /api/users/{id}` — Update user fields.
- `DELETE /api/users/{id}` — Soft-delete (set status=inactive).

#### 4. Settings Router (`/api/settings`)
- `GET /api/settings/{user_id}` — Retrieve settings (returns defaults if none exist).
- `PUT /api/settings/{user_id}` — Save/update settings (partial update supported).

#### 5. AI Suggestions (added to Files Router)
- `POST /api/files/{file_id}/suggest-tags` — LLM-based tag suggestions from file content.
- `POST /api/files/{file_id}/suggest-rename` — LLM-based rename suggestions.

### Frontend Changes

#### Dashboard
- Replace hardcoded `salesData`, `queryTrend`, `deptActivity`, `RECENT_ACTIVITIES` with API calls to `/api/dashboard/analytics`.
- Replace "Penjualan vs Target" BarChart with "Request/Query per Department" BarChart.
- Add loading skeletons and error fallback states.

#### Chat Page
- Add `VisualizationTransform` component that detects markdown tables, numeric patterns, and lists.
- Add auto-save logic: create session on first message, persist each message after.
- Add pagination to session list (SessionList component): page_size=20, "Load More" button.

#### Search Page
- Fix SearchResults component to properly call `/api/search/combined` and handle the response schema.
- Add department filter and minimum score filter.
- Add error state and empty state handling.

#### Knowledge Base
- Add "View Mode" toggle (flat/grouped).
- Implement grouping logic by file type and by department.
- Add file extension icon mapping utility.

#### File Explorer
- Add "Suggest Tags" button to MetadataSidebar.
- Add "Suggest Rename" button to MetadataSidebar.
- Display suggestions as interactive chips/options.

#### Graph Page
- Already has correct UI components — will work once backend `/api/graph` router exists.

#### Ingestion Dashboard
- Fix FileUpload component to include department dropdown populated from `/api/departments`.
- Ensure proper error handling for 413/422 responses.

#### Admin Users Page
- Replace `useState<User[]>(INITIAL_USERS)` with API fetch from `/api/users`.
- Connect all CRUD actions to backend endpoints.

#### Settings Page
- Add `useEffect` to load settings from `/api/settings/{user_id}` on mount.
- Change `handleSave` to PUT to backend instead of only updating local state.

## Correctness Properties

### Property 1: Dashboard Analytics Consistency
- **Criteria covered:** 1.1, 1.2, 1.3
- **Property:** The sum of per-department query counts returned by the analytics endpoint SHALL equal the total daily query count. The recent activities list SHALL contain at most 10 items and be ordered by timestamp descending.
- **Type:** Invariant

### Property 2: User CRUD Round-Trip
- **Criteria covered:** 13.1, 13.3, 13.5
- **Property:** Creating a user via POST /api/users and then retrieving via GET /api/users/{id} SHALL return the same name, email, role, department, and status. The password_hash field SHALL never appear in GET responses. The password_hash stored SHALL verify against the original plaintext using bcrypt.
- **Type:** Round-trip

### Property 3: Settings Partial Update Preservation
- **Criteria covered:** 15.1, 15.5
- **Property:** Updating a single settings section via PUT /api/settings/{user_id} SHALL not modify other previously-saved sections. Saving and retrieving settings SHALL produce equivalent values (round-trip).
- **Type:** Round-trip + Idempotence

### Property 4: Session Pagination Invariant
- **Criteria covered:** 5.1
- **Property:** For any page_size P and total sessions N, the GET /api/sessions endpoint SHALL return at most P items per page, and iterating all pages SHALL yield exactly N unique sessions with no duplicates and no omissions.
- **Type:** Invariant

### Property 5: Graph Relationship CRUD Consistency
- **Criteria covered:** 10.3, 10.4, 11.5
- **Property:** After creating a relationship via POST /api/graph/relationships, the GET /api/graph response SHALL include an edge matching source, target, and type. After deleting a relationship, it SHALL no longer appear. The auto-reference endpoint SHALL not suggest relationships that already exist.
- **Type:** Round-trip + Invariant

### Property 6: Search Result Filter Correctness
- **Criteria covered:** 6.4
- **Property:** When search results are filtered by department, all returned results SHALL have a source file belonging to that department. When filtered by minimum score, all returned results SHALL have a relevance score >= the threshold.
- **Type:** Metamorphic

### Property 7: File Extension Icon Mapping Totality
- **Criteria covered:** 7.4, 7.5
- **Property:** For any file extension string, the icon mapping function SHALL return a valid icon component. Known extensions (pdf, xlsx, xls, csv, docx, txt, png, jpg, tiff, md, json) SHALL each map to a distinct, non-generic icon. Unknown extensions SHALL map to the generic file icon.
- **Type:** Invariant

### Property 8: AI Auto-Reference Threshold
- **Criteria covered:** 11.3, 11.5
- **Property:** All relationships suggested by the auto-reference endpoint SHALL have a similarity confidence score >= 0.7. No suggested relationship SHALL have both source_file_id and target_file_id matching an existing relationship in the file_relationships table.
- **Type:** Invariant

### Property 9: Password Security Invariant
- **Criteria covered:** 13.3
- **Property:** For any plaintext password provided during user creation, the stored password_hash SHALL not equal the plaintext. The bcrypt.checkpw(plaintext, stored_hash) SHALL return True.
- **Type:** Round-trip

### Property 10: Document Grouping Completeness
- **Criteria covered:** 7.2, 7.3
- **Property:** When documents are grouped by file type, the union of all group members SHALL equal the complete document set (no documents lost). The same invariant SHALL hold when grouping by department.
- **Type:** Invariant

## File Structure

### New Backend Files
```
backend/app/
├── models/
│   ├── user.py                    # User SQLAlchemy model
│   ├── user_settings.py           # UserSettings SQLAlchemy model
│   └── file_relationship.py       # FileRelationship SQLAlchemy model
├── routers/
│   ├── dashboard.py               # Dashboard analytics router
│   ├── graph.py                   # Knowledge graph router
│   ├── users.py                   # User management router
│   └── settings.py                # Settings persistence router
├── schemas/
│   ├── dashboard.py               # Dashboard Pydantic schemas
│   ├── graph.py                   # Graph Pydantic schemas
│   ├── user.py                    # User Pydantic schemas
│   └── settings.py                # Settings Pydantic schemas
└── services/
    ├── dashboard_service.py       # Dashboard aggregation logic
    ├── graph_service.py           # Graph computation + layout
    ├── user_service.py            # User business logic
    └── ai_suggestion_service.py   # Tag/rename/auto-ref AI logic
```

### New/Modified Frontend Files
```
frontend/src/
├── api/
│   ├── dashboard.ts               # Dashboard API client
│   ├── users.ts                   # Users API client
│   └── settings.ts                # Settings API client
├── app/components/
│   ├── DashboardPage.tsx          # Modified: real data
│   ├── AdminUsersPage.tsx         # Modified: API integration
│   ├── SettingsPage.tsx           # Modified: API persistence
│   ├── SearchPage.tsx             # Modified: fix search
│   ├── chatplayground/
│   │   └── VisualizationTransform.tsx  # New: response visualizer
│   ├── ingestion/
│   │   └── FileUpload.tsx         # Modified: dept dropdown
│   └── explorer/
│       └── MetadataSidebar.tsx    # Modified: suggest buttons
├── hooks/
│   ├── useDashboard.ts            # New: dashboard data hook
│   ├── useUsers.ts                # New: users CRUD hook
│   └── useSettings.ts             # New: settings hook
└── utils/
    ├── fileIcons.ts               # New: extension→icon mapping
    └── visualizationDetector.ts   # New: structured data detection
```
