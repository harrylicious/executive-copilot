import { Sun, Moon, LogOut, Building2 } from "lucide-react";

export interface UserProfile {
  name: string;
  role: "staff" | "executive" | "admin";
  department: string;
  avatar: string;
}

interface MinimalHeaderProps {
  user: UserProfile;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onLogout: () => void;
}

export function MinimalHeader({ user, theme, onToggleTheme, onLogout }: MinimalHeaderProps) {
  return (
    <header className="sticky top-0 z-30 h-14 flex items-center justify-between px-5 border-b border-border/60 bg-card/40 backdrop-blur-sm">
      {/* Left side: App branding */}
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#10b981] to-[#059669] shadow-sm shadow-[#059669]/20 flex items-center justify-center shrink-0">
          <Building2 size={15} className="text-white" />
        </div>
        <div className="min-w-0">
          <div className="text-foreground font-semibold text-sm tracking-tight truncate">JB Executive Copilot</div>
        </div>
      </div>

      {/* Right side: User info + controls */}
      <div className="flex items-center gap-2">
        <span className="text-secondary-foreground text-xs font-medium hidden sm:inline mr-1">{user.name}</span>
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-primary-foreground text-[10px] font-semibold shrink-0 shadow-sm">
          {user.avatar}
        </div>
        <button
          onClick={onToggleTheme}
          className="text-muted-foreground/60 hover:text-secondary-foreground p-1.5 rounded-lg hover:bg-muted/50 transition-all"
          title={theme === "dark" ? "Mode Terang" : "Mode Gelap"}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
        </button>
        <button
          onClick={onLogout}
          className="text-muted-foreground/60 hover:text-[#f85149] p-1.5 rounded-lg hover:bg-[#f85149]/5 transition-all"
          title="Logout"
          aria-label="Logout"
        >
          <LogOut size={14} />
        </button>
      </div>
    </header>
  );
}
