import { useState } from "react";
import {
  Building2, MessageSquare, Database, Users, Settings,
  LayoutDashboard, ChevronRight, LogOut, Bell, Shield,
  Menu, X, Layers, Sun, Moon, Search, GitBranch, Upload
} from "lucide-react";

export interface UserProfile {
  name: string;
  role: "staff" | "executive" | "admin";
  department: string;
  avatar: string;
}

interface SidebarProps {
  user: UserProfile;
  currentPage: string;
  onNavigate: (page: string) => void;
  onLogout: () => void;
  theme: "dark" | "light";
  onToggleTheme: () => void;
}

interface NavItem {
  id: string;
  label: string;
  icon: typeof LayoutDashboard;
  roles: string[];
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Utama",
    items: [
      { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["staff", "executive", "admin"] },
      { id: "chat", label: "Copilot Chat", icon: MessageSquare, roles: ["staff", "executive", "admin"] },
      { id: "search", label: "Search", icon: Search, roles: ["staff", "executive", "admin"] },
    ],
  },
  {
    label: "Knowledge",
    items: [
      { id: "knowledge", label: "Knowledge Base", icon: Database, roles: ["staff", "executive", "admin"] },
      { id: "explorer", label: "File Explorer", icon: Search, roles: ["staff", "executive", "admin"] },
      { id: "graph", label: "Knowledge Graph", icon: GitBranch, roles: ["admin", "executive"] },
    ],
  },
  {
    label: "Administrasi",
    items: [
      { id: "ingestion", label: "Ingestion", icon: Upload, roles: ["admin"] },
      { id: "users", label: "Manajemen User", icon: Users, roles: ["admin"] },
      { id: "departments", label: "Departemen", icon: Layers, roles: ["admin", "executive"] },
      { id: "settings", label: "Pengaturan", icon: Settings, roles: ["staff", "executive", "admin"] },
    ],
  },
];

const ROLE_LABELS: Record<string, string> = { staff: "Staff", executive: "Eksekutif", admin: "Administrator" };
const ROLE_COLORS: Record<string, string> = { staff: "#10b981", executive: "#f59e0b", admin: "#059669" };

export function Sidebar({ user, currentPage, onNavigate, onLogout, theme, onToggleTheme }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const visibleGroups = NAV_GROUPS.map(group => ({
    ...group,
    items: group.items.filter(i => i.roles.includes(user.role)),
  })).filter(group => group.items.length > 0);

  const inner = (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="px-4 py-4 flex items-center gap-3 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shrink-0">
          <Building2 size={16} className="text-primary-foreground" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="text-foreground font-semibold text-xs truncate">JB Executive</div>
            <div className="text-primary text-[10px] tracking-widest truncate">COPILOT</div>
          </div>
        )}
        <button onClick={() => setCollapsed(!collapsed)}
          className="ml-auto text-muted-foreground hover:text-secondary-foreground hidden lg:block shrink-0">
          <ChevronRight size={14} className={`transition-transform ${collapsed ? "" : "rotate-180"}`} />
        </button>
      </div>

      {/* Nav items grouped */}
      <nav className="flex-1 px-2 py-3 overflow-y-auto">
        {visibleGroups.map((group, gi) => (
          <div key={group.label} className={gi > 0 ? "mt-4" : ""}>
            {!collapsed && (
              <div className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {group.label}
              </div>
            )}
            {collapsed && gi > 0 && (
              <div className="mx-3 mb-2 border-t border-border" />
            )}
            <div className="space-y-0.5">
              {group.items.map(item => {
                const active = currentPage === item.id;
                return (
                  <button key={item.id} onClick={() => { onNavigate(item.id); setMobileOpen(false); }}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left group ${
                      active
                        ? "bg-secondary text-primary border border-border"
                        : "text-muted-foreground hover:text-secondary-foreground hover:bg-card"
                    }`}>
                    <item.icon size={16} className={active ? "text-primary" : "text-muted-foreground group-hover:text-secondary-foreground"} />
                    {!collapsed && <span className="text-sm truncate">{item.label}</span>}
                    {!collapsed && active && <ChevronRight size={12} className="ml-auto text-primary" />}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Role badge */}
      {!collapsed && (
        <div className="px-3 py-2 mx-2 mb-2 rounded-lg bg-card border border-border">
          <div className="flex items-center gap-2">
            <Shield size={12} style={{ color: ROLE_COLORS[user.role] }} />
            <span className="text-xs" style={{ color: ROLE_COLORS[user.role] }}>{ROLE_LABELS[user.role]}</span>
            {user.role !== "admin" && (
              <span className="text-muted-foreground text-xs ml-auto">· {user.department}</span>
            )}
          </div>
        </div>
      )}

      {/* User profile */}
      <div className="px-2 pb-3 pt-2 border-t border-border">
        <div className={`flex items-center gap-3 px-2 py-2 rounded-lg ${collapsed ? "justify-center" : ""}`}>
          <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xs font-medium shrink-0">
            {user.avatar}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <div className="text-secondary-foreground text-xs font-medium truncate">{user.name}</div>
              <div className="text-muted-foreground text-[11px] truncate">{user.department}</div>
            </div>
          )}
          {!collapsed && (
            <div className="flex gap-1 shrink-0">
              <button onClick={onToggleTheme} className="text-muted-foreground hover:text-secondary-foreground p-1 rounded" title={theme === "dark" ? "Mode Terang" : "Mode Gelap"}>
                {theme === "dark" ? <Sun size={13} /> : <Moon size={13} />}
              </button>
              <button className="text-muted-foreground hover:text-secondary-foreground p-1 rounded">
                <Bell size={13} />
              </button>
              <button onClick={onLogout} className="text-muted-foreground hover:text-[#f85149] p-1 rounded">
                <LogOut size={13} />
              </button>
            </div>
          )}
          {collapsed && (
            <button onClick={onToggleTheme} className="w-full text-muted-foreground hover:text-secondary-foreground p-1 rounded flex justify-center" title={theme === "dark" ? "Mode Terang" : "Mode Gelap"}>
              {theme === "dark" ? <Sun size={13} /> : <Moon size={13} />}
            </button>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile hamburger */}
      <button onClick={() => setMobileOpen(true)}
        className="lg:hidden fixed top-4 left-4 z-50 bg-card border border-border rounded-lg p-2 text-secondary-foreground">
        <Menu size={16} />
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 bg-black/60" onClick={() => setMobileOpen(false)}>
          <div className="w-64 h-full bg-background border-r border-border"
            onClick={e => e.stopPropagation()}>
            <div className="flex justify-end p-3">
              <button onClick={() => setMobileOpen(false)} className="text-muted-foreground hover:text-secondary-foreground">
                <X size={16} />
              </button>
            </div>
            {inner}
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <aside className={`hidden lg:flex flex-col h-screen bg-background border-r border-border transition-all duration-200 shrink-0 ${collapsed ? "w-16" : "w-56"}`}>
        {inner}
      </aside>
    </>
  );
}
