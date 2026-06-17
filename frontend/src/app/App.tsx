import { useState, useEffect } from "react";
import { Toaster } from "sonner";
import { LoginPage } from "./components/LoginPage";
import { Sidebar } from "./components/Sidebar";
import type { UserProfile } from "./components/Sidebar";
import { MinimalHeader } from "./components/MinimalHeader";
import { getInitialPage, isPagePermitted } from "../utils/pagePermissions";
import { DashboardPage } from "./components/DashboardPage";
import { ChatPage } from "./components/ChatPage";
import { KnowledgeBasePage } from "./components/KnowledgeBasePage";
import { AdminUsersPage } from "./components/AdminUsersPage";
import { DepartmentsPage } from "./components/DepartmentsPage";
import { SettingsPage } from "./components/SettingsPage";
import { ExplorerPage } from "./components/ExplorerPage";
import { GraphPage } from "./components/GraphPage";
import { SearchPage } from "./components/SearchPage";
import { IngestionDashboard } from "./components/ingestion/IngestionDashboard";
import MonitoringDashboard from "./components/MonitoringDashboard";

export type ChatbotSettings = {
  language: "id" | "en";
  nuance: "formal" | "santai" | "profesional" | "ramah" | "tegas";
  restrictCrossDept: boolean;
  deptKeywords: Record<string, string[]>;
};

export default function App() {
  const [user, setUser] = useState<UserProfile | null>(() => {
    const stored = localStorage.getItem("jb-user");
    if (stored) {
      try { return JSON.parse(stored) as UserProfile; } catch { /* ignore corrupt data */ }
    }
    return null;
  });
  const [page, setPage] = useState(() => {
    const stored = localStorage.getItem("jb-user");
    if (stored) {
      try {
        const u = JSON.parse(stored) as UserProfile;
        return getInitialPage(u);
      } catch {
        return "chat";
      }
    }
    return "chat";
  });
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    return (localStorage.getItem("jb-theme") as "dark" | "light") || "dark";
  });
  const DEFAULT_SETTINGS: ChatbotSettings = {
    language: "id",
    nuance: "formal",
    restrictCrossDept: true,
    deptKeywords: {
      "Accounting Tax": ["pajak", "tax", "akuntansi", "perpajakan", "fiskal"],
      "Demand Supply": ["penjualan", "sales", "permintaan", "demand", "supply", "pengadaan"],
      Finance: ["keuangan", "anggaran", "budget", "investasi", "treasury", "cash flow"],
      Logistic: ["gudang", "warehouse", "inventaris", "pengiriman", "distribusi"],
    },
  };
  const [chatbotSettings, setChatbotSettings] = useState<ChatbotSettings>(() => {
    const stored = localStorage.getItem("jb-chatbot-settings");
    if (stored) {
      try { return { ...DEFAULT_SETTINGS, ...JSON.parse(stored) }; } catch { /* ignore corrupt data */ }
    }
    return DEFAULT_SETTINGS;
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("jb-theme", theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem("jb-chatbot-settings", JSON.stringify(chatbotSettings));
  }, [chatbotSettings]);

  const toggleTheme = () => setTheme(t => t === "dark" ? "light" : "dark");

  const navigateTo = (targetPage: string) => {
    if (!user) return;
    if (!isPagePermitted(user.role, targetPage)) {
      setPage("chat");
      return;
    }
    setPage(targetPage);
    if (user.role === "admin") {
      localStorage.setItem("jb-page", targetPage);
    }
  };

  // Handle role change during session
  useEffect(() => {
    if (user && user.role !== "admin") {
      localStorage.removeItem("jb-page");
      if (!isPagePermitted(user.role, page)) {
        setPage("chat");
      }
    }
  }, [user?.role]);

  if (!user) {
    return     <LoginPage onLogin={(u) => { localStorage.setItem("jb-user", JSON.stringify(u)); setUser(u); setPage("chat"); }} />;
  }

  const renderPage = () => {
    switch (page) {
      case "dashboard": return <DashboardPage user={user} onNavigate={navigateTo} />;
      case "chat": return <ChatPage user={user} chatbotSettings={chatbotSettings} onChatbotSettingsChange={setChatbotSettings} />;
      case "knowledge": return <KnowledgeBasePage user={user} />;
      case "users": return user.role === "admin" ? <AdminUsersPage /> : <DashboardPage user={user} onNavigate={navigateTo} />;
      case "departments": return (user.role === "admin" || user.role === "executive") ? <DepartmentsPage user={user} /> : <DashboardPage user={user} onNavigate={navigateTo} />;
      case "settings": return <SettingsPage user={user} chatbotSettings={chatbotSettings} onChatbotSettingsChange={setChatbotSettings} />;
      case "explorer": return <ExplorerPage />;
      case "graph": return <GraphPage />;
      case "search": return <SearchPage />;
      case "ingestion": return user.role === "admin" ? <IngestionDashboard /> : <DashboardPage user={user} onNavigate={navigateTo} />;
      case "monitoring": return user.role === "admin" ? <MonitoringDashboard /> : <DashboardPage user={user} onNavigate={navigateTo} />;
      default: return <DashboardPage user={user} onNavigate={navigateTo} />;
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("jb-user");
    localStorage.removeItem("jb-page");
    localStorage.removeItem("jb-chatbot-settings");
    setUser(null);
    setPage("chat");
  };

  // Non-admin users: MinimalHeader + full-width Chat
  if (user.role !== "admin") {
    return (
      <div className="flex flex-col h-screen bg-background overflow-hidden">
        <MinimalHeader user={user} theme={theme} onToggleTheme={toggleTheme} onLogout={handleLogout} />
        <main className="flex-1 overflow-hidden">
          <ChatPage user={user} chatbotSettings={chatbotSettings} onChatbotSettingsChange={setChatbotSettings} />
        </main>
        <Toaster position="top-right" theme={theme} richColors />
      </div>
    );
  }

  // Admin users: Sidebar + content area
  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar
        user={user}
        currentPage={page}
        onNavigate={navigateTo}
        onLogout={handleLogout}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
      <main className="flex-1 overflow-y-auto">
        {renderPage()}
      </main>
      <Toaster position="top-right" theme={theme} richColors />
    </div>
  );
}
