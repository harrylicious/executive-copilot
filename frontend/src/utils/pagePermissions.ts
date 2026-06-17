import type { UserProfile } from "../app/components/Sidebar";

/**
 * All valid page identifiers in the application.
 */
export const VALID_PAGES = [
  "dashboard",
  "chat",
  "knowledge",
  "users",
  "departments",
  "settings",
  "explorer",
  "graph",
  "search",
  "ingestion",
  "monitoring",
] as const;

/**
 * Union type of all valid page identifiers.
 */
export type PageId = (typeof VALID_PAGES)[number];

/**
 * Maps each role to the set of pages that role is permitted to access.
 */
export const PAGE_PERMISSIONS: Record<string, string[]> = {
  staff: ["chat", "settings"],
  executive: ["chat", "settings", "departments"],
  admin: [
    "dashboard",
    "chat",
    "knowledge",
    "users",
    "departments",
    "settings",
    "explorer",
    "graph",
    "search",
    "ingestion",
    "monitoring",
  ],
};

/**
 * Returns the list of page identifiers accessible to a given role.
 * Returns an empty array for unknown roles.
 */
export function getPermittedPages(role: string): string[] {
  return PAGE_PERMISSIONS[role] ?? [];
}

/**
 * Returns whether a specific page is accessible for the given role.
 */
export function isPagePermitted(role: string, page: string): boolean {
  return getPermittedPages(role).includes(page);
}

/**
 * Determines the initial page on session restore.
 * - Non-admin users: always returns "chat".
 * - Admin users: reads "jb-page" from localStorage, validates against VALID_PAGES,
 *   returns the stored value if valid or "chat" if invalid/missing.
 */
export function getInitialPage(user: UserProfile): string {
  if (user.role !== "admin") {
    return "chat";
  }

  const storedPage = localStorage.getItem("jb-page");

  if (storedPage && (VALID_PAGES as readonly string[]).includes(storedPage)) {
    return storedPage;
  }

  return "chat";
}
