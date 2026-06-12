# JB Copilot — Executive Copilot Chatbot

> AI-powered executive assistant for PT. Jembatan Baru. Query departmental data, visualize insights, and get source-attributed answers — all with role-based access control.

Built from a Figma design spec, the app simulates a fully functional enterprise copilot with login, dashboard, multi-department knowledge base chat, data visualization, user management, department administration, and settings — all running client-side with mock data.

**Design reference:** [Figma — Executive Copilot Chatbot](https://www.figma.com/design/b2gBJurTcJF6WgQ1yOjrSE/Executive-Copilot-Chatbot)

---

## Table of Contents

- [Features](#features)
- [Screens & Routes](#screens--routes)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Build & Preview](#build--preview)
- [Demo Credentials](#demo-credentials)
- [Role-Based Access](#role-based-access)
- [Chatbot Configuration](#chatbot-configuration)
- [Theming](#theming)
- [Design Assets](#design-assets)

---

## Features

### 🔐 Role-Based Access Control
Three user roles with distinct permissions:
- **Admin** — Full access: dashboard, chat (all departments), user management, department management, settings
- **Executive** — Dashboard, chat (all departments or scoped), department management, settings
- **Staff** — Dashboard, chat (own department only), knowledge base (own department only), settings

### 💬 AI-Powered Chat (Mock)
- Ask questions in **Indonesian** (primary) or **English**
- Responses come with **data tables** and **interactive charts** (bar, line, pie, stacked bar)
- Toggle between *text*, *table*, and *chart* views on any response
- Every answer cites **source documents** with a built-in **file viewer** for drill-down

### 🚫 Cross-Department Query Blocking
Staff accounts cannot query other departments' data. The chatbot detects cross-department intent via keyword matching and returns a policy-blocked message in the configured tone.

### 🎭 Multi-Nuance Responses
Choose from 5 conversational tones in Settings:

| Nuance | ID | EN |
|--------|----|----|
| **Formal** | Bahasa baku, struktur lengkap | Formal, complete sentences |
| **Santai** | Bahasa sehari-hari, akrab | Casual, colloquial |
| **Profesional** | Fokus data, efisien | Professional, to-the-point |
| **Ramah** | Hangat, suportif | Warm, inviting |
| **Tegas** | Langsung, tanpa basa-basi | Firm, direct |

### 📊 Dashboard Analytics
- KPI cards (document count, daily queries, AI accuracy)
- Sales vs target bar chart
- Per-department activity pie chart (executive/admin)
- Daily query trend line chart (staff)
- Recent activity feed
- Quick-action buttons (Start Chat, Upload Document)

### 📁 Knowledge Base Management
- Document listing with status indicators (processed/processing/failed)
- Department and status filters
- Drag-and-drop upload simulation
- Inline file viewer with document content preview

### 👥 Admin Features
- User management (add, edit, delete, search, filter)
- Role assignment (Staff / Executive / Admin)
- Department management with CRUD operations
- Department head assignment and member counts

### ⚙️ Settings
- Profile editing
- Password change (mock)
- Notification preferences
- **Chatbot configuration:**
  - Language toggle (Indonesian / English)
  - Nuance selector
  - Cross-department restriction toggle
  - Per-department keyword editor for cross-dept detection

### 🌓 Dark / Light Theme
Persistent theme toggle available in the sidebar. Preference saved to `localStorage`.

---

## Screens & Routes

| Page | Route (via sidebar) | Role Access | Description |
|------|---------------------|-------------|-------------|
| **Login** | Initial | — | Email/password login with demo account shortcuts |
| **Dashboard** | `dashboard` | All | KPI cards, charts, activity feed, quick actions |
| **Copilot Chat** | `chat` | All | AI chat with multi-view responses, source file viewer, department scope selector |
| **Knowledge Base** | `knowledge` | All | Document listing, upload, file viewer |
| **Manajemen User** | `users` | Admin only | User CRUD table with role filtering |
| **Departemen** | `departments` | Admin, Executive | Department CRUD with detail view |
| **Pengaturan** | `settings` | All | Profile, chatbot config, notifications |

---

## Tech Stack

| Category | Libraries |
|----------|-----------|
| **Core** | React 18, TypeScript 5, React DOM 18 |
| **Bundler** | Vite 6, `@vitejs/plugin-react` |
| **Styling** | Tailwind CSS v4 (`@tailwindcss/vite`), Emotion 11, MUI 7 |
| **UI / Headless** | Radix UI primitives (40+ components), shadcn/ui patterns |
| **Icons** | Lucide React |
| **Charts** | Recharts |
| **Forms** | react-hook-form |
| **Date** | date-fns, react-day-picker |
| **Animation** | Motion (Framer Motion), canvas-confetti |
| **Drag & Drop** | react-dnd + react-dnd-html5-backend |
| **Carousel** | Embla Carousel |
| **Overlays** | Vaul (drawer), Sonner (toast) |
| **Layout** | react-resizable-panels, react-responsive-masonry |
| **Utility** | clsx, class-variance-authority, tailwind-merge, cmdk, input-otp |

---

## Project Structure

```
frontend_new/
├── index.html                          # Entry HTML
├── vite.config.ts                      # Vite config with @ alias, Tailwind, Figma asset resolver
├── postcss.config.mjs                  # PostCSS config
├── package.json                        # Dependencies & scripts
├── pnpm-workspace.yaml                 # pnpm workspace config
├── default_shadcn_theme.css            # shadcn/ui default theme variables
├── ATTRIBUTIONS.md                     # Third-party attributions (shadcn/ui, Unsplash)
├── guidelines/
│   └── Guidelines.md                   # Figma design guidelines
├── dist/                               # Build output
├── node_modules/
└── src/
    ├── main.tsx                        # App entry point
    ├── styles/
    │   ├── index.css                   # Styles entry (imports fonts, tailwind, theme)
    │   ├── fonts.css                   # Custom font faces
    │   ├── tailwind.css                # Tailwind directives (@tailwind base/components/utilities)
    │   ├── theme.css                   # CSS custom properties for dark/light theme
    │   └── globals.css                 # Global resets and base styles
    └── app/
        ├── App.tsx                     # Root component: routing, auth state, theme, chatbot settings
        └── components/
            ├── LoginPage.tsx           # Login with brand panel, demo accounts
            ├── Sidebar.tsx             # Navigation sidebar (collapsible, role-filtered, mobile responsive)
            ├── DashboardPage.tsx       # KPI cards, charts, activity feed, quick actions
            ├── ChatPage.tsx            # Full chat interface with multi-view responses and file viewer
            ├── KnowledgeBasePage.tsx   # Document listing with upload, filters, status indicators
            ├── AdminUsersPage.tsx      # User management CRUD
            ├── DepartmentsPage.tsx     # Department management CRUD
            ├── SettingsPage.tsx        # Profile, chatbot config, notifications
            ├── FileViewer.tsx          # Document preview modal with page content and table view
            ├── ui/                     # 48 shadcn/ui components
            │   ├── button.tsx, dialog.tsx, card.tsx, form.tsx, table.tsx, ...
            │   └── utils.ts           # cn() helper (clsx + tailwind-merge)
            └── figma/
                └── ImageWithFallback.tsx  # Image component with fallback (from Figma export)
```

---

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The dev server starts at **`http://localhost:5173`**.

### Available Scripts

| Script | Command | Description |
|--------|---------|-------------|
| `dev` | `vite` | Start dev server with HMR |
| `build` | `vite build` | Production build to `dist/` |

---

## Build & Preview

```bash
# Production build
npm run build

# Preview the build locally (requires `npm run build` first)
npx vite preview
```

---

## Demo Credentials

Use any of these accounts on the login screen:

| Email | Password | Role | Department |
|-------|----------|------|------------|
| `admin@jembatanbaru.co.id` | `admin123` | **Admin** | Accounting Tax |
| `director@jembatanbaru.co.id` | `exec123` | **Executive** | Board |
| `demand@jembatanbaru.co.id` | `demand123` | **Staff** | Demand Supply |
| `finance@jembatanbaru.co.id` | `finance123` | **Staff** | Finance |

You can also click **"Gunakan →"** on any demo account card to auto-fill credentials.

---

## Role-Based Access

| Page | Admin | Executive | Staff |
|------|-------|-----------|-------|
| Dashboard | ✅ (all dept data) | ✅ (all dept data) | ✅ (own dept only) |
| Copilot Chat | ✅ (all depts) | ✅ (all depts, scope selector) | ✅ (own dept, cross-dept blocked) |
| Knowledge Base | ✅ (all depts) | ✅ (all depts) | ✅ (own dept only) |
| Manajemen User | ✅ | ❌ | ❌ |
| Departemen | ✅ (full CRUD) | ✅ (view only) | ❌ |
| Pengaturan | ✅ | ✅ | ✅ |

### Cross-Department Blocking

When **Staff** users ask a question containing keywords from another department's configuration, the chat responds with a **blocked access** message (in the configured tone/language). This is enforced client-side via keyword matching — keywords are editable in Settings by admins.

---

## Chatbot Configuration

Accessible via **Settings → Chatbot** tab (visible to all roles).

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| **Language** | `id` / `en` | `id` | Response language |
| **Nuance** | 5 options | `formal` | Conversational tone |
| **Restrict Cross-Dept** | toggle | `on` | Block staff queries across departments |
| **Dept Keywords** | editable list | per-dept defaults | Keywords used to detect cross-dept intent |

Default department keywords:

| Department | Keywords |
|------------|----------|
| Accounting Tax | `pajak`, `tax`, `akuntansi`, `perpajakan`, `fiskal` |
| Demand Supply | `penjualan`, `sales`, `permintaan`, `demand`, `supply`, `pengadaan` |
| Finance | `keuangan`, `anggaran`, `budget`, `investasi`, `treasury`, `cash flow` |
| Logistic | `gudang`, `warehouse`, `inventaris`, `pengiriman`, `distribusi` |

---

## Theming

The app supports dark and light themes, controlled by a `data-theme` attribute on `<html>`:

| Attribute | Theme | Default |
|-----------|-------|---------|
| `data-theme="dark"` | Dark (default) | ✅ |
| `data-theme="light"` | Light | — |

The theme is persisted in `localStorage` under the key `jb-theme`. Toggle via the sun/moon icon in the sidebar footer.

CSS custom properties are defined in [`src/styles/theme.css`](src/styles/theme.css) and follow the shadcn/ui design token convention.

---

## Design Assets

This project was generated from a Figma design. Key design artifacts:

- **Original design:** [Executive Copilot Chatbot (Figma)](https://www.figma.com/design/b2gBJurTcJF6WgQ1yOjrSE/Executive-Copilot-Chatbot)
- **Figma asset resolver:** A custom Vite plugin resolves `figma:asset/` import specifiers — see [`vite.config.ts`](vite.config.ts)
- **Guidelines:** [`guidelines/Guidelines.md`](guidelines/Guidelines.md)
- **Attributions:** [`ATTRIBUTIONS.md`](ATTRIBUTIONS.md)

### Third-Party Components

- **shadcn/ui components** in [`src/app/components/ui/`](src/app/components/ui/) — Used under [MIT license](https://github.com/shadcn-ui/ui/blob/main/LICENSE.md)
- **Photos** from [Unsplash](https://unsplash.com) — Used under [Unsplash license](https://unsplash.com/license)
- Icons from **Lucide** (MIT)

---

## Notes

- This is a **client-only prototype** — all data is mocked in-memory. There is no backend API connection in `frontend_new/`.
- The companion **Knowledge Base Manager** backend (FastAPI + SQLAlchemy + ChromaDB + LangChain) lives in [`../eaip-layer1/`](../eaip-layer1/) and can serve as a real API backend for this frontend.
- Chart interactions (view toggling, chart type switching) operate on static mock data.
- The file upload in Knowledge Base simulates progress but does not persist.
