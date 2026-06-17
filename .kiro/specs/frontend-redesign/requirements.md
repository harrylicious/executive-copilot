# Requirements Document

## Introduction

This feature redesigns the frontend layout of the JB Executive Copilot application. The primary goals are to make the Chat page the default landing experience for all authenticated users and to restrict sidebar navigation visibility to admin users only. Non-admin users (staff, executive) receive a chat-focused interface with minimal UI controls for logout and theme switching.

## Glossary

- **App**: The root React component (`App.tsx`) that manages authentication state, page routing, and layout rendering.
- **Sidebar**: The navigation panel component that displays grouped navigation links, role badge, user profile section, theme toggle, and logout button.
- **Chat_Page**: The full-screen chat interface where users interact with the AI copilot.
- **User_Profile**: The authenticated user object returned by the backend containing name, role, department, and avatar fields.
- **Role**: A string field on User_Profile with possible values "staff", "executive", or "admin" that determines access permissions.
- **Non_Admin_User**: A user whose Role is "staff" or "executive".
- **Admin_User**: A user whose Role is "admin".
- **Default_Page**: The page displayed immediately after successful authentication.
- **Minimal_Header**: A lightweight UI bar displayed for Non_Admin_Users providing access to essential controls (logout, theme toggle) without full navigation.
- **Navigation_Group**: A labeled section within the Sidebar containing related navigation items (e.g., "Utama", "Knowledge", "Administrasi").

## Requirements

### Requirement 1: Default Page After Login

**User Story:** As a user, I want the Chat page to appear immediately after I log in, so that I can start interacting with the AI copilot without extra navigation steps.

#### Acceptance Criteria

1. WHEN a user successfully authenticates, THE App SHALL display the Chat_Page and set the active navigation indicator to Chat_Page.
2. WHEN the App loads and a valid user session is restored from the "jb-user" localStorage entry, THE App SHALL display the Chat_Page as the initial view.
3. IF the App loads and the "jb-user" localStorage entry contains invalid or unparseable data, THEN THE App SHALL discard the corrupt entry and display the Login_Page.

### Requirement 2: Sidebar Visibility for Admin Users

**User Story:** As an admin, I want to see the full sidebar navigation after login, so that I can access all management and knowledge pages.

#### Acceptance Criteria

1. WHILE the authenticated user is an Admin_User, THE App SHALL render the Sidebar component as a visible fixed-width panel on the left side of the viewport.
2. WHILE the authenticated user is an Admin_User, THE Sidebar SHALL display all Navigation_Groups that contain at least one navigation item permitted for the admin role, including "Utama", "Knowledge", and "Administrasi" groups.
3. WHILE the authenticated user is an Admin_User AND the current page is Chat_Page, THE App SHALL render the Sidebar in its standard left-panel position and the Chat_Page in the remaining viewport space without overlapping.
4. IF the authenticated user's Role changes from "admin" to a non-admin value during an active session, THEN THE App SHALL remove the Sidebar component and apply the Non_Admin_User layout.

### Requirement 3: Sidebar Hidden for Non-Admin Users

**User Story:** As a staff or executive user, I want a clean chat-focused interface without the sidebar, so that I can focus on my conversation with the AI copilot.

#### Acceptance Criteria

1. WHILE the authenticated user is a Non_Admin_User, THE App SHALL NOT include the Sidebar component in the rendered DOM.
2. WHILE the authenticated user is a Non_Admin_User, THE App SHALL render the Chat_Page content area at 100% of the viewport width with no left margin or padding reserved for the Sidebar.
3. IF the authenticated user's Role changes from "admin" to "staff" or "executive" during an active session, THEN THE App SHALL remove the Sidebar from the DOM and expand the Chat_Page content area to 100% of the viewport width within 1 second of the role change being received.

### Requirement 4: Minimal Header for Non-Admin Users

**User Story:** As a non-admin user, I want access to logout and theme toggle controls, so that I can manage my session and display preferences without needing the full sidebar.

#### Acceptance Criteria

1. WHILE the authenticated user is a Non_Admin_User, THE App SHALL render a Minimal_Header component positioned at the top of the viewport above the Chat_Page content area.
2. THE Minimal_Header SHALL display a logout button that, when clicked, removes the "jb-user" entry from localStorage, resets the user state to null, and displays the Login_Page.
3. THE Minimal_Header SHALL display a theme toggle button that switches the application theme between "dark" and "light" modes, persisting the selection to the "jb-theme" localStorage key.
4. THE Minimal_Header SHALL display the user's name as text and a circular avatar derived from User_Profile.
5. THE Minimal_Header SHALL remain visible on all pages accessible to Non_Admin_Users without being scrolled away by page content.

### Requirement 5: Non-Admin Page Access Restrictions

**User Story:** As a non-admin user, I want the interface to only show pages I have permission to access, so that I am not confused by unavailable features.

#### Acceptance Criteria

1. WHILE the authenticated user has Role "staff", THE App SHALL restrict accessible pages to Chat_Page and Settings page only.
2. WHILE the authenticated user has Role "executive", THE App SHALL restrict accessible pages to Chat_Page, Settings page, and Departments page only.
3. IF a Non_Admin_User attempts to navigate to a page outside the permitted set for their Role, THEN THE App SHALL redirect the user to Chat_Page without rendering any content from the restricted page.
4. IF a Non_Admin_User attempts to navigate to a page outside the permitted set by modifying persisted page state in local storage, THEN THE App SHALL redirect the user to Chat_Page on session restore.

### Requirement 6: Admin Layout with Chat as Default

**User Story:** As an admin, I want Chat to be my default landing page while still having full sidebar navigation, so that I can quickly start chatting but also navigate to admin tools.

#### Acceptance Criteria

1. WHEN an Admin_User successfully authenticates, THE App SHALL display the Chat_Page rendered within the standard sidebar layout, with the Sidebar visible alongside the Chat_Page content area.
2. WHILE the authenticated user is an Admin_User AND the current page is Chat_Page, THE Sidebar SHALL apply the active navigation style (bg-secondary, text-primary, border) to the Chat navigation item.
3. THE Sidebar SHALL include a navigation item for Chat_Page within the "Utama" Navigation_Group, positioned as the first item in the group, with the roles field set to include "admin".
4. WHILE the authenticated user is an Admin_User AND the current page is Chat_Page, THE App SHALL NOT render the Chat_Page using the full-screen layout path that bypasses the Sidebar.

### Requirement 7: Floating Action Button Removal

**User Story:** As a user, I want a consistent interface without redundant navigation elements, so that the UI feels clean and purposeful.

#### Acceptance Criteria

1. WHILE any user is authenticated, THE App SHALL NOT render a floating action button for navigating to Chat_Page on any page.
2. WHILE the authenticated user is an Admin_User, THE Sidebar SHALL provide the navigation entry point to Chat_Page within the "Utama" Navigation_Group as the replacement for the removed floating action button.
3. WHILE the authenticated user is a Non_Admin_User, THE Chat_Page SHALL be the Default_Page and accessible without a dedicated navigation element, since Non_Admin_Users land on Chat_Page by default and can return to it via the Minimal_Header or page redirect.

### Requirement 8: Session Persistence of Page State

**User Story:** As an admin user, I want my last visited page to be remembered when I reload the browser, so that I can continue where I left off.

#### Acceptance Criteria

1. WHEN an Admin_User navigates to a page, THE App SHALL persist the current page identifier to local storage under the key "jb-page", where the page identifier is one of: "dashboard", "chat", "knowledge", "users", "departments", "settings", "explorer", "graph", "search", "ingestion", or "monitoring".
2. WHEN an Admin_User session is restored from local storage and the "jb-page" key contains a valid page identifier, THE App SHALL display the page corresponding to the persisted identifier instead of defaulting to Chat_Page.
3. IF an Admin_User session is restored from local storage and the "jb-page" key is missing, empty, or contains a value not in the valid page identifier list, THEN THE App SHALL display Chat_Page.
4. WHEN a Non_Admin_User session is restored from local storage, THE App SHALL display Chat_Page regardless of any persisted page state in "jb-page".
5. WHEN an Admin_User logs out, THE App SHALL remove the "jb-page" key from local storage.
