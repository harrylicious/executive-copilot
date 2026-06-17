import { useState } from "react";
import {
  Building2, Users, Settings,
  LayoutDashboard, ChevronRight, LogOut, Bell, Shield,
  Menu, X, Layers, Sun, Moon, Search, GitBranch, Upload, Activity, MessageSquare
} from "lucide-react";
import { cn } from "./ui/utils";

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
      { id: "chat", label: "Copilot", icon: MessageSquare, roles: ["staff", "executive", "admin"] },
      { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["staff", "executive", "admin"] },
    ],
  },
  {
    label: "Knowledge",
    items: [
      { id: "explorer", label: "File Explorer", icon: Search, roles: ["staff", "executive", "admin"] },
      { id: "graph", label: "Knowledge Graph", icon: GitBranch, roles: ["admin", "executive"] },
    ],
  },
  {
    label: "Administrasi",
    items: [
      { id: "ingestion", label: "Ingestion", icon: Upload, roles: ["admin"] },
      { id: "monitoring", label: "Embedding Monitor", icon: Activity, roles: ["admin"] },
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
      <div className="px-4 py-4 flex items-center gap-3 border-b border-border/60">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#10b981] to-[#059669] shadow-lg shadow-[#059669]/20 flex items-center justify-center shrink-0">
          <Building2 size={16} className="text-white" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <div className="text-foreground font-bold text-xs truncate tracking-tight">JB Executive</div>
            <div className="text-[#10b981] text-[9px] tracking-[0.2em] uppercase truncate font-semibold">Copilot</div>
          </div>
        )}
        <button onClick={() => setCollapsed(!collapsed)}
          className="ml-auto text-muted-foreground/50 hover:text-secondary-foreground hidden lg:block shrink-0 p-1 rounded-lg hover:bg-muted/50 transition-all">
          <ChevronRight size={14} className={`transition-transform duration-200 ${collapsed ? "" : "rotate-180"}`} />
        </button>
      </div>

      {/* Nav items grouped */}
      <nav className="flex-1 px-2 py-3 overflow-y-auto custom-scrollbar">
        {visibleGroups.map((group, gi) => (
          <div key={group.label} className={gi > 0 ? "mt-4" : ""}>
            {!collapsed && (
              <div className="px-3 mb-1.5 text-[9px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/50">
                {group.label}
              </div>
            )}
            {collapsed && gi > 0 && (
              <div className="mx-3 mb-2 border-t border-border/40" />
            )}
            <div className="space-y-0.5">
              {group.items.map(item => {
                const active = currentPage === item.id;
                return (
                  <button key={item.id} onClick={() => { onNavigate(item.id); setMobileOpen(false); }}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all text-left group ${
                      active
                        ? "bg-gradient-to-r from-primary/10 to-transparent text-primary border border-primary/15 shadow-sm"
                        : "text-muted-foreground/70 hover:text-secondary-foreground hover:bg-muted/40"
                    }`}>
                    <div className={cn(
                      "w-6 h-6 rounded-lg flex items-center justify-center shrink-0 transition-all",
                      active
                        ? "bg-primary/15 text-primary"
                        : "text-muted-foreground/60 group-hover:text-secondary-foreground"
                    )}>
                      <item.icon size={14} />
                    </div>
                    {!collapsed && (
                      <span className="text-xs font-medium truncate">{item.label}</span>
                    )}
                    {!collapsed && active && (
                      <ChevronRight size={10} className="ml-auto text-primary/60" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Role badge */}
      {!collapsed && (
        <div className="px-3 py-2 mx-2 mb-2 rounded-xl bg-card/70 border border-border/50">
          <div className="flex items-center gap-2">
            <div className={cn(
              "w-5 h-5 rounded-lg flex items-center justify-center",
              user.role === "admin" ? "bg-[#059669]/10" : user.role === "executive" ? "bg-[#f59e0b]/10" : "bg-[#10b981]/10"
            )}>
              <Shield size={10} style={{ color: ROLE_COLORS[user.role] }} />
            </div>
            <span className="text-xs font-medium" style={{ color: ROLE_COLORS[user.role] }}>{ROLE_LABELS[user.role]}</span>
            {user.role !== "admin" && (
              <span className="text-muted-foreground/60 text-[10px] ml-auto truncate">· {user.department}</span>
            )}
          </div>
        </div>
      )}

      {/* User profile */}
      <div className="px-2 pb-3 pt-2 border-t border-border/50">
        <div className={`flex items-center gap-3 px-2 py-2 rounded-xl ${collapsed ? "justify-center" : ""}`}>
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-primary-foreground text-xs font-semibold shrink-0 shadow-sm">
            {user.avatar}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <div className="text-secondary-foreground text-xs font-medium truncate">{user.name}</div>
              <div className="text-muted-foreground/60 text-[10px] truncate">{user.department}</div>
            </div>
          )}
          {!collapsed && (
            <div className="flex gap-0.5 shrink-0">
              <button onClick={onToggleTheme} className="text-muted-foreground/50 hover:text-secondary-foreground p-1.5 rounded-lg hover:bg-muted/50 transition-all" title={theme === "dark" ? "Mode Terang" : "Mode Gelap"}>
                {theme === "dark" ? <Sun size={12} /> : <Moon size={12} />}
              </button>
              <button className="text-muted-foreground/50 hover:text-secondary-foreground p-1.5 rounded-lg hover:bg-muted/50 transition-all">
                <Bell size={12} />
              </button>
              <button onClick={onLogout} className="text-muted-foreground/50 hover:text-[#f85149] p-1.5 rounded-lg hover:bg-[#f85149]/5 transition-all">
                <LogOut size={12} />
              </button>
            </div>
          )}
          {collapsed && (
            <button onClick={onToggleTheme} className="w-full text-muted-foreground/50 hover:text-secondary-foreground p-1.5 rounded-lg hover:bg-muted/50 transition-all flex justify-center" title={theme === "dark" ? "Mode Terang" : "Mode Gelap"}>
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
        className="lg:hidden fixed top-4 left-4 z-50 bg-card border border-border/60 rounded-xl p-2.5 text-secondary-foreground shadow-sm">
        <Menu size={16} />
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 bg-black/70 backdrop-blur-sm" onClick={() => setMobileOpen(false)}>
          <div className="w-64 h-full bg-background border-r border-border/60"
            onClick={e => e.stopPropagation()}>
            <div className="flex justify-end p-3">
              <button onClick={() => setMobileOpen(false)} className="text-muted-foreground hover:text-secondary-foreground p-1.5 rounded-lg hover:bg-muted/50 transition-all">
                <X size={16} />
              </button>
            </div>
            {inner}
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <aside className={`hidden lg:flex flex-col h-screen bg-background border-r border-border/60 transition-all duration-200 shrink-0 ${collapsed ? "w-16" : "w-56"}`}>
        {inner}
      </aside>
    </>
  );
}


