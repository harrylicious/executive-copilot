import { useState, useEffect } from "react";
import { Sun, Moon } from "lucide-react";
import { Toaster } from "sonner";
import { LoginPage } from "./components/LoginPage";
import { Sidebar } from "./components/Sidebar";
import type { UserProfile } from "./components/Sidebar";
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
  const [page, setPage] = useState("dashboard");
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    return (localStorage.getItem("jb-theme") as "dark" | "light") || "dark";
  });
  const [chatbotSettings, setChatbotSettings] = useState<ChatbotSettings>({
    language: "id",
    nuance: "formal",
    restrictCrossDept: true,
    deptKeywords: {
      "Accounting Tax": ["pajak", "tax", "akuntansi", "perpajakan", "fiskal"],
      "Demand Supply": ["penjualan", "sales", "permintaan", "demand", "supply", "pengadaan"],
      Finance: ["keuangan", "anggaran", "budget", "investasi", "treasury", "cash flow"],
      Logistic: ["gudang", "warehouse", "inventaris", "pengiriman", "distribusi"],
    },
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("jb-theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme(t => t === "dark" ? "light" : "dark");

  if (!user) {
    return     <LoginPage onLogin={(u) => { localStorage.setItem("jb-user", JSON.stringify(u)); setUser(u); setPage("dashboard"); }} />;
  }

  const renderPage = () => {
    switch (page) {
      case "dashboard": return <DashboardPage user={user} onNavigate={setPage} />;
      case "chat": return <ChatPage user={user} chatbotSettings={chatbotSettings} />;
      case "knowledge": return <KnowledgeBasePage user={user} />;
      case "users": return user.role === "admin" ? <AdminUsersPage /> : <DashboardPage user={user} onNavigate={setPage} />;
      case "departments": return (user.role === "admin" || user.role === "executive") ? <DepartmentsPage user={user} /> : <DashboardPage user={user} onNavigate={setPage} />;
      case "settings": return <SettingsPage user={user} chatbotSettings={chatbotSettings} onChatbotSettingsChange={setChatbotSettings} />;
      case "explorer": return <ExplorerPage />;
      case "graph": return <GraphPage />;
      case "search": return <SearchPage />;
      case "ingestion": return user.role === "admin" ? <IngestionDashboard /> : <DashboardPage user={user} onNavigate={setPage} />;
      default: return <DashboardPage user={user} onNavigate={setPage} />;
    }
  };

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar
        user={user}
        currentPage={page}
        onNavigate={setPage}
        onLogout={() => { localStorage.removeItem("jb-user"); setUser(null); setPage("dashboard"); }}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
      <main className={`flex-1 overflow-y-auto ${page === "chat" ? "overflow-hidden" : ""}`}>
        {renderPage()}
      </main>
      <Toaster position="top-right" theme={theme} richColors />
    </div>
  );
}
