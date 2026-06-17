# Implementation Plan: Frontend Redesign

## Overview

Restructure the JB Executive Copilot frontend to make Chat the default landing page, implement role-based layout rendering (sidebar for admins, minimal header for non-admins), enforce page access restrictions by role, remove the floating action button, and persist page state for admin users. The implementation targets the existing React + Vite + Tailwind CSS stack with TypeScript.

## Tasks

- [x] 1. Set up testing infrastructure and define shared constants
  - [x] 1.1 Install test framework and property-based testing dependencies
    - Add vitest, @testing-library/react, @testing-library/jest-dom, jsdom, and fast-check as devDependencies
    - Create vitest.config.ts with jsdom environment and setup file
    - Create test setup file with @testing-library/jest-dom imports
    - _Requirements: Testing Strategy (design)_

  - [x] 1.2 Create shared page permission constants and helper functions
    - Create `frontend/src/utils/pagePermissions.ts`
    - Define `PAGE_PERMISSIONS` record mapping roles to permitted page arrays
    - Define `VALID_PAGES` const array with all valid page identifiers
    - Implement `getPermittedPages(role: string): string[]` helper
    - Implement `isPagePermitted(role: string, page: string): boolean` helper
    - Implement `getInitialPage(user: UserProfile): string` that reads `jb-page` from localStorage for admins and always returns `"chat"` for non-admins
    - Export `PageId` type union from this module
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 8.1, 8.2, 8.3, 8.4_

- [x] 2. Implement MinimalHeader component for non-admin users
  - [x] 2.1 Create the MinimalHeader component
    - Create `frontend/src/app/components/MinimalHeader.tsx`
    - Accept props: `user: UserProfile`, `theme: "dark" | "light"`, `onToggleTheme: () => void`, `onLogout: () => void`
    - Render sticky header at top with `position: sticky; top: 0; z-index: 30` and height `h-14`
    - Left side: App logo/title (JB Executive Copilot branding)
    - Right side: User name text, circular avatar from `user.avatar`, theme toggle button (Sun/Moon icons), logout button (LogOut icon)
    - Apply `border-b border-border` bottom border and background matching app theme
    - Ensure the header does not scroll away with page content
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 2.2 Write property test for MinimalHeader user identity display
    - **Property 10: MinimalHeader displays user identity**
    - **Validates: Requirements 4.4**

- [x] 3. Modify Sidebar to include Chat navigation item
  - [x] 3.1 Add Chat nav item to Utama group in Sidebar
    - Import `MessageSquare` icon from lucide-react
    - Add `{ id: "chat", label: "Chat", icon: MessageSquare, roles: ["admin"] }` as the **first item** in the "Utama" NavGroup
    - Ensure the active navigation style (`bg-secondary text-primary border border-border`) applies when `currentPage === "chat"`
    - _Requirements: 6.2, 6.3, 7.2_

- [x] 4. Refactor App.tsx for role-based layout and Chat as default
  - [x] 4.1 Update App.tsx default page initialization and login handler
    - Change initial `page` state from `"dashboard"` to `"chat"`
    - Modify the login callback to set page to `"chat"` instead of `"dashboard"`
    - Import and use `getInitialPage` from `pagePermissions.ts` for session restore logic
    - On session restore: if user is admin, read and validate `jb-page` from localStorage; if non-admin, always set page to `"chat"`
    - Handle invalid/corrupt `jb-user` localStorage: discard and set user to null (existing logic, verify coverage)
    - _Requirements: 1.1, 1.2, 1.3, 8.2, 8.3, 8.4_

  - [x] 4.2 Implement role-based layout branching in App.tsx
    - For admin users: render `Sidebar` + `<main>` content area (existing layout structure)
    - For non-admin users: render `MinimalHeader` + full-width Chat content without Sidebar in DOM
    - Remove the full-screen chat bypass (`if (page === "chat")` block that returns early)
    - Admin chat page renders within the sidebar layout (using `renderPage` switch case)
    - Non-admin layout: content area uses `100%` viewport width with no sidebar margin
    - _Requirements: 2.1, 2.3, 3.1, 3.2, 4.1, 6.1, 6.4_

  - [x] 4.3 Remove the floating action button
    - Delete the `motion.button` element with `MessageSquare` icon and `"Buka Copilot Chat"` title
    - Remove the `motion` import from `"motion/react"` if no longer used elsewhere
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 4.4 Add page access enforcement and page persistence
    - Import `isPagePermitted` and `PAGE_PERMISSIONS` from `pagePermissions.ts`
    - Wrap `setPage` calls with permission check: if page not permitted for role, redirect to `"chat"`
    - For admin users: persist page to `localStorage.setItem("jb-page", page)` on every valid navigation
    - For non-admin users: ignore `jb-page` localStorage value on restore, always use `"chat"`
    - On admin logout: remove `"jb-page"` from localStorage (in addition to `"jb-user"`)
    - Handle role change during session: if role becomes non-admin, remove sidebar, clear `jb-page`, force page to `"chat"` if current page not permitted
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 8.1, 8.2, 8.4, 8.5, 2.4, 3.3_

- [x] 5. Checkpoint - Verify core functionality
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Write property-based tests for page permissions and session logic
  - [ ]* 6.1 Write property test for page permission enforcement
    - **Property 4: Page permission enforcement**
    - Generate random (role, page) pairs including valid and invalid page identifiers
    - Verify that for any role R and page P: if P not in permitted set for R, result is "chat"; if P is in permitted set, result is P
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [ ]* 6.2 Write property test for non-admin session restore
    - **Property 5: Non-admin session restore always yields Chat**
    - Generate random non-admin users and arbitrary `jb-page` localStorage values (valid pages, invalid strings, empty, missing)
    - Verify `getInitialPage` always returns "chat" for non-admin roles
    - **Validates: Requirements 1.2, 5.4, 8.4**

  - [ ]* 6.3 Write property test for admin page persistence round-trip
    - **Property 6: Admin page persistence round-trip**
    - Generate random valid pages from admin's permitted set
    - Persist to localStorage, then call `getInitialPage` for admin user
    - Verify stored page is correctly restored
    - **Validates: Requirements 8.1, 8.2**

  - [ ]* 6.4 Write property test for admin invalid page restore
    - **Property 7: Admin invalid page restore defaults to Chat**
    - Generate arbitrary strings NOT in VALID_PAGES
    - Store in `jb-page`, call `getInitialPage` for admin user
    - Verify result is "chat"
    - **Validates: Requirements 8.3**

  - [ ]* 6.5 Write property test for corrupt session data
    - **Property 2: Corrupt session data results in unauthenticated state**
    - Generate arbitrary strings (invalid JSON, valid JSON with missing fields, invalid role values)
    - Verify session restore produces null user state
    - **Validates: Requirements 1.3**

  - [ ]* 6.6 Write property test for theme toggle round-trip
    - **Property 9: Theme toggle persistence round-trip**
    - Generate random initial theme values, invoke toggle, verify new theme is opposite and persisted to `jb-theme`
    - **Validates: Requirements 4.3**

- [ ] 7. Write unit tests for components and integration
  - [ ]* 7.1 Write unit tests for App layout rendering
    - Test: admin login renders Sidebar + Chat page within sidebar layout
    - Test: staff login renders MinimalHeader + full-width Chat, no Sidebar in DOM
    - Test: executive login renders MinimalHeader + full-width Chat, no Sidebar in DOM
    - Test: no floating action button in any authenticated view
    - Test: Chat nav item shows active styling when page is "chat" for admin
    - _Requirements: 2.1, 3.1, 6.1, 6.4, 7.1_

  - [ ]* 7.2 Write unit tests for MinimalHeader component
    - Test: logout button clears localStorage and resets user state
    - Test: theme toggle switches between dark/light and persists to jb-theme
    - Test: displays user name and avatar
    - Test: header is sticky and visible
    - _Requirements: 4.2, 4.3, 4.4, 4.5_

  - [ ]* 7.3 Write unit tests for page permissions and session persistence
    - Test: staff can only access chat and settings pages
    - Test: executive can access chat, settings, and departments
    - Test: navigating to restricted page redirects to chat
    - Test: admin page persistence saves and restores correctly
    - Test: admin logout clears jb-page from localStorage
    - _Requirements: 5.1, 5.2, 5.3, 8.1, 8.2, 8.5_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The project currently has no test framework; task 1.1 sets up vitest + fast-check from scratch
- All TypeScript code follows the existing project conventions (Vite + React 18 + Tailwind CSS + Radix UI)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "3.1"] },
    { "id": 2, "tasks": ["2.2", "4.1"] },
    { "id": 3, "tasks": ["4.2", "4.3"] },
    { "id": 4, "tasks": ["4.4"] },
    { "id": 5, "tasks": ["6.1", "6.2", "6.3", "6.4", "6.5", "6.6"] },
    { "id": 6, "tasks": ["7.1", "7.2", "7.3"] }
  ]
}
```
