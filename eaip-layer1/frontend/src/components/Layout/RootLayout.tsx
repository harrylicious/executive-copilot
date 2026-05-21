import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { SidebarContentContext } from "./SidebarContentContext";
import type { ReactNode } from "react";

/**
 * RootLayout: single left sidebar (nav + optional page content) + main area.
 */
export function RootLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarContent, setSidebarContent] = useState<ReactNode>(null);

  return (
    <SidebarContentContext.Provider value={setSidebarContent}>
      <div className="h-screen flex overflow-hidden bg-background text-foreground">
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed((prev) => !prev)}
        >
          {sidebarContent}
        </Sidebar>
        <main className="flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </SidebarContentContext.Provider>
  );
}

export default RootLayout;
