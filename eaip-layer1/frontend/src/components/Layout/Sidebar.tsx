import { type FC, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  FolderOpen,
  Network,
  MessageSquare,
  Search,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";

const NAV_ITEMS = [
  { label: "Explorer", path: "/", icon: FolderOpen },
  { label: "Graph", path: "/graph", icon: Network },
  { label: "Playground", path: "/playground", icon: MessageSquare },
  { label: "Search", path: "/search", icon: Search },
] as const;

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  children?: ReactNode;
}

export const Sidebar: FC<SidebarProps> = ({ collapsed, onToggle, children }) => {
  const location = useLocation();

  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  };

  return (
    <aside
      className={cn(
        "flex flex-col h-full border-r border-border bg-card transition-all duration-200 shrink-0 overflow-hidden",
        collapsed ? "w-12" : "w-60"
      )}
    >
      {/* Header: Brand + Toggle */}
      <div
        className={cn(
          "flex items-center h-11 border-b border-border shrink-0",
          collapsed ? "justify-center px-0" : "px-3 gap-2"
        )}
      >
        {!collapsed && (
          <span className="text-xs font-bold text-primary truncate tracking-wide">
            JB Executive Copilot
          </span>
        )}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onToggle}
          className={cn(!collapsed && "ml-auto")}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeftOpen className="size-4" />
          ) : (
            <PanelLeftClose className="size-4" />
          )}
        </Button>
      </div>

      {/* Navigation */}
      <nav className="py-1.5 space-y-0.5 px-1.5 shrink-0">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.path);
          return (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                "flex items-center gap-2.5 rounded-md text-sm font-medium transition-colors",
                collapsed ? "justify-center h-8 w-8 mx-auto" : "px-2.5 h-7",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="size-3.5 shrink-0" />
              {!collapsed && <span className="truncate text-xs">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Page-specific content (e.g. file explorer) */}
      {!collapsed && children && (
        <div className="flex-1 overflow-hidden border-t border-border">
          {children}
        </div>
      )}

      {/* Spacer when no children */}
      {(!children || collapsed) && <div className="flex-1" />}

      {/* Bottom: Theme toggle */}
      <div
        className={cn(
          "border-t border-border py-1.5 shrink-0",
          collapsed ? "flex justify-center" : "px-2"
        )}
      >
        <ThemeToggle />
      </div>
    </aside>
  );
};

export default Sidebar;
