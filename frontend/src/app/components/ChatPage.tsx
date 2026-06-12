import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import {
  Send, Paperclip, BarChart2, Table, AlignLeft, Copy, ThumbsUp,
  ThumbsDown, RefreshCw, Bot, ChevronDown, Sparkles, LayoutList, PanelLeft, Plus,
  Loader2, FileText, AlertCircle, Eye, Type
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } from "recharts";
import { marked } from "marked";
import { toast } from "sonner";
import type { UserProfile } from "./Sidebar";
import type { ChatbotSettings } from "../App";
import { FileViewer } from "./FileViewer";
import { streamChat, type ChatStreamEvent } from "../../api/chat";
import { getSession, saveSession } from "../../api/kb";
import { SessionList } from "./SessionList";
import { VisualizationTransform } from "./chatplayground/VisualizationTransform";
import { detectMarkdownTable, detectNumericData, detectList } from "../../utils/visualizationDetector";

// Configure marked
marked.setOptions({ breaks: true, gfm: true });

/* ---------- types ---------- */

interface Source {
  title: string;
  dept: string;
  page?: number;
}

interface RetrievalMeta {
  queryTimeMs: number;
  documentsRetrieved: number;
  retrievalMode: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  sources?: Source[];
  suggestions?: string[];
  metadata?: RetrievalMeta;
  isComplete?: boolean;
  isStreaming?: boolean;
  error?: string;
  /** Legacy mock-only fields */
  tableData?: Array<Record<string, string | number>>;
  chartData?: Array<Record<string, string | number>>;
  chartType?: "bar" | "line" | "pie" | "stacked";
  viewMode?: "text" | "table" | "chart";
  blocked?: boolean;
}

/* ---------- mock data ---------- */

const SUGGESTIONS = [
  "Apa performa penjualan bulan Juni 2024?",
  "Bandingkan pendapatan Q1 vs Q2 2024",
  "Siapa top 5 sales performer kuartal ini?",
  "Berapa total anggaran operasional yang tersisa?",
];

const CROSS_DEPT_SUGGESTIONS = [
  "Bagaimana status inventaris gudang?",
  "Berapa total pengeluaran pajak tahun ini?",
  "Tunjukkan data logistik pengiriman terbaru",
];

const MOCK_TABLE = [
  { region: "DKI Jakarta", jan: 1240, feb: 1380, mar: 1520, total: 4140 },
  { region: "Jawa Barat", jan: 890, feb: 920, mar: 1050, total: 2860 },
  { region: "Jawa Timur", jan: 760, feb: 810, mar: 940, total: 2510 },
  { region: "Sumatera Utara", jan: 540, feb: 590, mar: 680, total: 1810 },
  { region: "Bali", jan: 420, feb: 450, mar: 510, total: 1380 },
];

const PIE_COLORS = ["#10b981", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444"];

const BLOCKED_MESSAGES: Record<ChatbotSettings["nuance"], { id: string; en: string }> = {
  formal: {
    id: "Mohon maaf, pertanyaan Anda memerlukan akses ke data dari departemen lain yang tidak tercakup dalam wewenang Anda. Berdasarkan kebijakan perusahaan, Staff hanya dapat mengakses data dari departemen sendiri. Silakan hubungi atasan atau Administrator untuk mengajukan permintaan akses lintas departemen.",
    en: "Sorry, your query requires access to data from another department which is outside your authority. Per company policy, Staff can only access their own department's data. Please contact your supervisor or Administrator to request cross-department access.",
  },
  santai: {
    id: "Maaf ya, pertanyaan lo butuh akses ke data departemen lain. Nah, aturannya staff cuma bisa lihat data departemen sendiri. Coba hubungi bos lo atau Admin buat minta akses.",
    en: "Sorry, your question needs data from another department. Rules say staff can only see their own department's data. Try reaching out to your boss or Admin to request access.",
  },
  profesional: {
    id: "Akses ditolak. Pertanyaan ini memerlukan data lintas departemen yang tidak tersedia untuk role Anda. Staff —> terbatas pada departemen sendiri. Ajukan ke atasan untuk perubahan akses.",
    en: "Access denied. This query requires cross-department data not available for your role. Staff are limited to their own department. Escalate to your supervisor for access changes.",
  },
  ramah: {
    id: "Wah, maaf! Sepertinya kamu butuh data dari departemen lain, tapi akun Staff kamu hanya bisa mengakses data departemen sendiri. Coba diskusi dengan atasan atau tim Admin ya, siapa tahu bisa dibantu!",
    en: "Oops, sorry! It looks like you need data from another department, but your Staff account can only access your own department's data. Try discussing with your supervisor or the Admin team — they might be able to help!",
  },
  tegas: {
    id: "PERHATIAN: Sistem mendeteksi pertanyaan Anda memerlukan data dari departemen lain. Kebijakan keamanan melarang akses tersebut untuk role Staff. Ajukan permohonan akses ke Administrator.",
    en: "WARNING: System detected your query requires data from another department. Security policy prohibits such access for Staff role. Submit an access request to the Administrator.",
  },
};

interface Props { user: UserProfile; chatbotSettings: ChatbotSettings; }

const NUANCE_PROMPTS: Record<ChatbotSettings["nuance"], { id: string; en: string }> = {
  formal: { id: "Dengan hormat, berikut adalah data yang Saudara minta.", en: "With due respect, here is the data you requested." },
  santai: { id: "Oke, nih data yang lo minta.", en: "Here you go, the data you asked for." },
  profesional: { id: "Berikut ringkasan data yang diminta.", en: "Here is the requested data summary." },
  ramah: { id: "Tentu, dengan senang hati! Berikut informasinya.", en: "Sure, happy to help! Here is the information." },
  tegas: { id: "Catat: berikut data yang perlu Anda perhatikan.", en: "Note: here is the data you need to review." },
};

const NUANCE_BODIES: Record<ChatbotSettings["nuance"], { id: string; en: string }> = {
  formal: { id: "", en: "" },
  santai: { id: "", en: "" },
  profesional: { id: "", en: "" },
  ramah: { id: "", en: "" },
  tegas: { id: "", en: "" },
};

/* ---------- sub-components ---------- */

function MarkdownContent({ content }: { content: string }) {
  const html = useMemo(() => {
    try {
      return marked.parse(content) as string;
    } catch {
      return content;
    }
  }, [content]);
  return (
    <div
      className="prose prose-sm dark:prose-invert max-w-none text-foreground prose-p:my-1.5 prose-headings:my-2 prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5 prose-pre:my-2 prose-code:text-xs prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-muted prose-pre:border prose-pre:border-border prose-a:text-primary prose-blockquote:border-primary/30"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

interface ResponseViewProps {
  msg: Message;
  onViewChange: (id: string, view: "text" | "table" | "chart", chartType?: "bar" | "line" | "pie" | "stacked") => void;
  onSourceClick: (source: Source) => void;
  onSuggestionClick: (text: string) => void;
}

function ResponseView({ msg, onViewChange, onSourceClick, onSuggestionClick }: ResponseViewProps) {
  const hasTable = !!msg.tableData;
  const hasChart = !!msg.chartData;
  const view = msg.viewMode || "text";

  return (
    <div>
      {/* Blocked banner */}
      {msg.blocked && (
        <div className="flex items-start gap-3 mb-3 p-3 bg-[rgba(248,81,73,0.1)] border border-[rgba(248,81,73,0.2)] rounded-xl">
          <div className="w-7 h-7 rounded-lg bg-[rgba(248,81,73,0.15)] flex items-center justify-center shrink-0 mt-0.5">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f85149" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
          </div>
          <div>
            <div className="text-[#f85149] text-xs font-medium mb-0.5">Akses Dibatasi</div>
            <div className="text-secondary-foreground text-sm leading-relaxed whitespace-pre-line">{msg.content}</div>
          </div>
        </div>
      )}

      {/* Error state */}
      {msg.error && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-destructive/10 border border-destructive/20">
          <AlertCircle className="size-3.5 text-destructive shrink-0" />
          <span className="text-xs text-destructive">{msg.error}</span>
        </div>
      )}

      {/* View toggle (mock table/chart only) */}
      {!msg.blocked && !msg.error && (hasTable || hasChart) && (
        <div className="flex gap-1 mb-3">
          {(["text", "table", "chart"] as const).filter(v => v === "text" || (v === "table" && hasTable) || (v === "chart" && hasChart)).map(v => (
            <button key={v} onClick={() => onViewChange(msg.id, v)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs transition-all ${
                view === v ? "bg-[#059669] text-white" : "bg-input text-muted-foreground hover:text-secondary-foreground"
              }`}>
              {v === "text" && <><AlignLeft size={11} />Teks</>}
              {v === "table" && <><Table size={11} />Tabel</>}
              {v === "chart" && <><BarChart2 size={11} />Grafik</>}
            </button>
          ))}
        </div>
      )}

      {/* Markdown content */}
      {!msg.blocked && !msg.error && view === "text" && msg.content && (
        <MarkdownContent content={msg.content} />
      )}

      {/* Streaming indicator */}
      {msg.isStreaming && !msg.content && (
        <div className="flex items-center gap-2 text-muted-foreground py-2">
          <Loader2 size={14} className="animate-spin" />
          <span className="text-xs">Menulis jawaban...</span>
        </div>
      )}

      {/* Table view (mock only) */}
      {!msg.blocked && view === "table" && msg.tableData && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-xs">
            <thead className="bg-secondary">
              <tr>
                {Object.keys(msg.tableData[0]).map(k => (
                  <th key={k} className="px-3 py-2 text-left text-muted-foreground font-medium capitalize border-b border-border">{k}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {msg.tableData.map((row, i) => (
                <tr key={i} className={i % 2 === 0 ? "bg-card" : "bg-background"}>
                  {Object.values(row).map((v, j) => (
                    <td key={j} className="px-3 py-2 text-secondary-foreground border-b border-border">
                      {typeof v === "number" ? v.toLocaleString("id-ID") : v}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Chart view (mock only) */}
      {!msg.blocked && view === "chart" && msg.chartData && (
        <div className="bg-background rounded-lg p-3 border border-border">
          <div className="flex gap-1 mb-2">
            {(["bar", "line", "pie", "stacked"] as const).filter(t => {
              if (t === "stacked") return msg.tableData && Object.keys(msg.tableData[0]).length > 2;
              return true;
            }).map(ct => (
              <button key={ct} onClick={() => onViewChange(msg.id, "chart", ct)}
                className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-all ${
                  (msg.chartType || "bar") === ct ? "bg-primary text-primary-foreground" : "bg-input text-muted-foreground hover:text-secondary-foreground"
                }`}>
                {ct === "bar" && <BarChart2 size={11} />}
                {ct === "line" && <BarChart2 size={11} />}
                {ct === "pie" && <PieChart size={11} />}
                {ct === "stacked" && <LayoutList size={11} />}
                {ct === "bar" ? "Bar" : ct === "line" ? "Line" : ct === "pie" ? "Pie" : "Stacked"}
              </button>
            ))}
          </div>
          <ResponsiveContainer width="100%" height={200}>
            {msg.chartType === "pie" ? (
              <PieChart>
                <Pie data={msg.chartData} dataKey={Object.keys(msg.chartData[0]).find(k => k !== "name" && k !== "region") || "value"}
                  cx="50%" cy="50%" outerRadius={80} strokeWidth={0}>
                  {msg.chartData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--foreground)", fontSize: 11 }} />
              </PieChart>
            ) : msg.chartType === "line" ? (
              <LineChart data={msg.chartData}>
                <XAxis dataKey={Object.keys(msg.chartData[0])[0]} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--foreground)", fontSize: 11 }} />
                {Object.keys(msg.chartData[0]).slice(1).map((k, i) => (
                  <Line key={k} type="monotone" dataKey={k} stroke={PIE_COLORS[i]} strokeWidth={2} dot={false} />
                ))}
              </LineChart>
            ) : msg.chartType === "stacked" && msg.tableData ? (
              <BarChart data={msg.tableData}>
                <XAxis dataKey={Object.keys(msg.tableData[0])[0]} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--foreground)", fontSize: 11 }} />
                {Object.keys(msg.tableData[0]).slice(1).filter(k => k !== "total").map((k, i) => (
                  <Bar key={k} dataKey={k} stackId="a" fill={PIE_COLORS[i % PIE_COLORS.length]} radius={[2, 2, 0, 0]} />
                ))}
              </BarChart>
            ) : (
              <BarChart data={msg.chartData}>
                <XAxis dataKey={Object.keys(msg.chartData[0])[0]} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--foreground)", fontSize: 11 }} />
                {Object.keys(msg.chartData[0]).slice(1).map((k, i) => (
                  <Bar key={k} dataKey={k} fill={PIE_COLORS[i]} radius={[4, 4, 0, 0]} />
                ))}
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      )}

      {/* Sources */}
      {!msg.blocked && msg.sources && msg.sources.length > 0 && view === "text" && (
        <div className="mt-3 pt-3 border-t border-border">
          <div className="text-muted-foreground text-xs mb-1.5 flex items-center gap-1">
            <FileText size={12} /> Sumber referensi
          </div>
          <div className="flex flex-wrap gap-2">
            {msg.sources.map((s, i) => (
              <button key={i} onClick={() => onSourceClick(s)}
                className="flex items-center gap-1.5 bg-secondary border border-border rounded-lg px-2.5 py-1 hover:border-primary/40 transition-colors text-left cursor-pointer">
                <span className="text-primary text-[10px] font-medium">[{i + 1}]</span>
                <span className="text-secondary-foreground text-[11px]">{s.title}</span>
                <span className="text-muted-foreground text-[10px]">· {s.dept}{s.page ? ` hal.${s.page}` : ""}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Metadata */}
      {msg.metadata && msg.isComplete && (
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground pt-2 mt-2 border-t border-border">
          {msg.metadata.queryTimeMs > 0 && <span>{msg.metadata.queryTimeMs}ms</span>}
          {msg.metadata.documentsRetrieved > 0 && <span>{msg.metadata.documentsRetrieved} dokumen</span>}
          {msg.metadata.retrievalMode && <span className="capitalize">{msg.metadata.retrievalMode}</span>}
        </div>
      )}

      {/* Follow-up suggestions */}
      {msg.suggestions && msg.suggestions.length > 0 && msg.isComplete && (
        <div className="pt-3 mt-2 space-y-1.5 border-t border-border">
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <Sparkles className="size-3" />
            <span>Pertanyaan lanjutan</span>
          </div>
          <div className="flex flex-col gap-1">
            {msg.suggestions.map((suggestion, idx) => (
              <button
                key={idx}
                onClick={() => onSuggestionClick(suggestion)}
                className="text-left text-xs px-2.5 py-1.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-muted hover:border-primary/30 transition-colors"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------- helper: detect structured data ---------- */

function hasStructuredData(content: string): boolean {
  if (!content) return false;
  return !!(detectMarkdownTable(content) || detectNumericData(content) || detectList(content));
}

/* ---------- main ChatPage ---------- */

export function ChatPage({ user, chatbotSettings }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedDept, setSelectedDept] = useState(user.role === "executive" || user.role === "admin" ? "all" : user.department);
  const [viewingSource, setViewingSource] = useState<{
    id: string; name: string; type: string; size: string; dept: string;
    uploadedBy: string; uploadedAt: string; pages?: number; chunks?: number; status?: string;
  } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef<string>(crypto.randomUUID());
  const titleRef = useRef<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  // Per-message view mode: "text" | "visual". Default to "visual" when structured data is detected.
  const [visualViewModes, setVisualViewModes] = useState<Record<string, "text" | "visual">>({});
  // Local queue of message IDs pending persistence confirmation (Requirement 4.4)
  const pendingQueueRef = useRef<Set<string>>(new Set());
  // Track whether session has been created (first message persisted)
  const sessionCreatedRef = useRef<boolean>(false);
  // Persistence lock to prevent concurrent saves
  const persistingRef = useRef<boolean>(false);

  const departments = user.role === "executive" || user.role === "admin"
    ? ["all", "Accounting Tax", "Demand Supply", "Finance", "Logistic"]
    : [user.department];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  /** Open the FileViewer for a source doc from the backend. We only know title + dept. */
  const handleSourceClick = (source: Source) => {
    const sourceId = Date.now().toString();
    setViewingSource({
      id: sourceId,
      name: source.title,
      dept: source.dept,
      type: source.title.split(".").pop()?.toLowerCase() || "txt",
      size: "—",
      uploadedBy: "—",
      uploadedAt: "—",
      pages: source.page,
    });
  };

  /** Click a follow-up suggestion  */
  const handleSuggestionClick = (text: string) => {
    sendMessage(text);
  };

  const sendMessage = async (text: string) => {
    if (!text.trim()) return;
    const userMsg: Message = { id: Date.now().toString(), role: "user", content: text, timestamp: new Date() };
    const isFirstMessage = messages.length === 0;
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    // Auto-create session on first message (Requirement 4.1)
    if (isFirstMessage) {
      const title = deriveTitle(text);
      titleRef.current = title;
      try {
        await saveSession({
          id: sessionIdRef.current,
          title,
          messages: [messageToRecord(userMsg, sessionIdRef.current)],
        });
        sessionCreatedRef.current = true;
      } catch (err) {
        console.error("Failed to create session:", err);
        // Session creation failed — add to pending queue for next attempt (Requirement 4.5)
        pendingQueueRef.current.add(userMsg.id);
      }
    } else if (sessionCreatedRef.current) {
      // Auto-persist user message for subsequent messages (Requirement 4.2)
      // Persist incrementally: save all messages including the new user message
      const allMsgs = [...messages, userMsg];
      persistCurrentSession(allMsgs);
    } else {
      // Session not yet created — queue the message for later persistence
      pendingQueueRef.current.add(userMsg.id);
    }

    // Cross-dept blocking check (mock)
    const isRestricted = user.role !== "executive" && user.role !== "admin" && chatbotSettings.restrictCrossDept;
    const lower = text.toLowerCase();
    let blockedDept: string | null = null;
    if (isRestricted) {
      for (const dept of Object.keys(chatbotSettings.deptKeywords)) {
        if (dept === user.department) continue;
        const match = chatbotSettings.deptKeywords[dept]?.some(kw => lower.includes(kw));
        if (match) { blockedDept = dept; break; }
      }
    }

    if (blockedDept) {
      const blockedMsg: Message = {
        id: (Date.now() + 1).toString(), role: "assistant",
        content: BLOCKED_MESSAGES[chatbotSettings.nuance][chatbotSettings.language],
        timestamp: new Date(), blocked: true, isComplete: true,
      };
      setMessages(prev => {
        const updated = [...prev, blockedMsg];
        // Auto-persist blocked response (Requirement 4.2)
        if (sessionCreatedRef.current) {
          persistCurrentSession(updated);
        }
        return updated;
      });
      setLoading(false);
      return;
    }

    // Create an empty assistant message for SSE streaming
    const assistantId = (Date.now() + 1).toString();
    const emptyMsg: Message = {
      id: assistantId, role: "assistant", content: "", timestamp: new Date(),
      sources: [], suggestions: [], isStreaming: true, isComplete: false,
    };
    setMessages(prev => [...prev, emptyMsg]);

    try {
      await streamChat(
        { query: text, language: chatbotSettings.language },
        (evt: ChatStreamEvent) => {
          switch (evt.event) {
            case "token":
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: m.content + (evt.data as { content: string }).content } : m
              ));
              break;
            case "sources":
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? {
                  ...m,
                  sources: (evt.data as { source_attributions: Array<{ file_name: string; department: string }> }).source_attributions.map(s => ({
                    title: s.file_name, dept: s.department,
                  })),
                } : m
              ));
              break;
            case "metadata":
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? {
                  ...m,
                  metadata: {
                    queryTimeMs: (evt.data as Record<string, number>).query_time_ms ?? 0,
                    documentsRetrieved: (evt.data as Record<string, number>).documents_retrieved ?? 0,
                    retrievalMode: (evt.data as Record<string, string>).retrieval_mode ?? "",
                  },
                } : m
              ));
              break;
            case "suggestions":
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? {
                  ...m,
                  suggestions: (evt.data as { suggestions: string[] }).suggestions,
                } : m
              ));
              break;
            case "done":
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, isStreaming: false, isComplete: true } : m
              ));
              break;
            case "error":
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, error: (evt.data as { message: string }).message, isStreaming: false } : m
              ));
              break;
          }
        }
      );
    } catch {
      // Backend unavailable — use mock fallback
      setMessages(prev => prev.filter(m => m.id !== assistantId));
      const scope = selectedDept === "all"
        ? (chatbotSettings.language === "id" ? "seluruh departemen" : "all departments")
        : (chatbotSettings.language === "id" ? `departemen ${selectedDept}` : `department ${selectedDept}`);
      const greeting = NUANCE_PROMPTS[chatbotSettings.nuance][chatbotSettings.language];
      const fallbackMsg: Message = {
        id: assistantId, role: "assistant", timestamp: new Date(),
        content: `${greeting}\n\nBerdasarkan analisis dari **${scope}**, berikut ringkasan data penjualan per wilayah:\n\n• **DKI Jakarta** memimpin dengan total **4.140 juta IDR** (Q1 2024)\n• **Jawa Barat** di posisi kedua dengan **2.860 juta IDR**\n• **Pertumbuhan tertinggi** di Jawa Timur (+24% MoM)`,
        sources: [
          { title: "Laporan Penjualan Q2 2024.xlsx", dept: "Demand Supply", page: 3 },
          { title: "Review Kinerja Bulanan.pdf", dept: "Demand Supply", page: 7 },
        ],
        suggestions: [
          "Tampilkan data dalam bentuk tabel",
          "Bandingkan dengan Q1 2024",
          "Wilayah mana yang perlu perbaikan?",
        ],
        tableData: MOCK_TABLE,
        chartData: MOCK_TABLE.map(r => ({ region: r.region, total: r.total })),
        chartType: "bar",
        isComplete: true,
        metadata: { queryTimeMs: 1240, documentsRetrieved: 5, retrievalMode: "combined" },
      };
      setMessages(prev => [...prev, fallbackMsg]);
    }
    // Auto-persist session after assistant response completes (Requirement 4.2)
    setMessages(prev => {
      // Persist the full conversation including the completed assistant message
      persistCurrentSession(prev);
      return prev;
    });
    setLoading(false);
  };

  const changeView = (id: string, view: "text" | "table" | "chart", chartType?: "bar" | "line" | "pie" | "stacked") => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, viewMode: view, ...(chartType ? { chartType } : {}) } : m));
  };

  /* ─── Session helpers ───────────────────────────────────────────────── */

  const deriveTitle = (content: string): string => {
    const trimmed = content.trim();
    if (trimmed.length <= 50) return trimmed;
    return trimmed.slice(0, 50);
  };

  const messageToRecord = (msg: Message, sessionId: string) => ({
    id: msg.id,
    sessionId,
    role: msg.role,
    content: msg.content,
    sources: msg.sources
      ? msg.sources.map((s) => ({ fileId: 0, fileName: s.title, department: s.dept, chunkIndex: s.page ?? 0 }))
      : null,
    metadataJson: msg.metadata ?? null,
    error: msg.error ?? null,
    timestamp: msg.timestamp.getTime(),
  });

  /**
   * Persist the current session to the backend with retry logic (Requirement 4.2 & 4.4).
   * Saves all persistable messages (user messages and completed assistant messages).
   * Retains unsent messages in local queue until persistence is confirmed.
   */
  const persistCurrentSession = useCallback(async (msgs: Message[], retryCount = 0): Promise<boolean> => {
    const sessionId = sessionIdRef.current;
    // Persistable: user messages always, assistant messages only when complete
    const persistableMessages = msgs.filter(
      (m) => (m.role === "user" && m.content.length > 0) || (m.role === "assistant" && m.isComplete && m.content.length > 0)
    );
    if (persistableMessages.length === 0) return true;

    if (!titleRef.current) {
      const firstUser = persistableMessages.find((m) => m.role === "user");
      if (firstUser) titleRef.current = deriveTitle(firstUser.content);
    }

    // Add all messages to pending queue
    persistableMessages.forEach((m) => pendingQueueRef.current.add(m.id));

    try {
      await saveSession({
        id: sessionId,
        title: titleRef.current,
        messages: persistableMessages.map((m) => messageToRecord(m, sessionId)),
      });
      // Persistence confirmed — remove from queue
      persistableMessages.forEach((m) => pendingQueueRef.current.delete(m.id));
      sessionCreatedRef.current = true;
      return true;
    } catch (err) {
      console.error(`Failed to persist session (attempt ${retryCount + 1}):`, err);
      // Retry with exponential backoff: 1s, 2s, 4s (Requirement 4.4)
      if (retryCount < 2) {
        const delay = Math.pow(2, retryCount) * 1000;
        await new Promise((resolve) => setTimeout(resolve, delay));
        return persistCurrentSession(msgs, retryCount + 1);
      }
      // All retries failed — show non-blocking warning toast (Requirement 4.4)
      toast.warning("Gagal menyimpan sesi chat. Pesan akan dicoba simpan kembali.", {
        duration: 5000,
      });
      // Messages remain in the pending queue for next retry opportunity
      return false;
    }
  }, []);

  const handleNewSession = () => {
    sessionIdRef.current = crypto.randomUUID();
    titleRef.current = null;
    sessionCreatedRef.current = false;
    pendingQueueRef.current.clear();
    setMessages([]);
    setRefreshKey((k) => k + 1);
  };

  const handleSelectSession = async (sessionId: string) => {
    try {
      const session = await getSession(sessionId);
      sessionIdRef.current = session.id;
      titleRef.current = session.title ?? null;
      sessionCreatedRef.current = true;
      pendingQueueRef.current.clear();
      const loaded: Message[] = (session.messages || []).map((record) => ({
        id: record.id,
        role: record.role as "user" | "assistant",
        content: record.content,
        timestamp: new Date(record.timestamp),
        sources: record.sources
          ? record.sources.map((s) => ({ title: s.fileName, dept: s.department, page: s.chunkIndex }))
          : undefined,
        metadata: record.metadataJson ?? undefined,
        error: record.error ?? undefined,
        isComplete: true,
        isStreaming: false,
      }));
      setMessages(loaded);
    } catch (err) {
      console.error("Failed to load session:", err);
    }
  };

  return (
    <div className="flex h-screen">
      {/* Session sidebar */}
      {sidebarOpen && (
        <SessionList
          activeSessionId={sessionIdRef.current}
          onSelect={handleSelectSession}
          onNewSession={handleNewSession}
          onClose={() => setSidebarOpen(false)}
          refreshKey={refreshKey}
        />
      )}

      {/* Main chat area */}
      <div className="flex flex-col flex-1 min-w-0">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border flex items-center gap-3 shrink-0">
        {!sidebarOpen && (
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors mr-1"
            title="Buka riwayat chat"
          >
            <PanelLeft className="size-4" />
          </button>
        )}
        <div className="w-8 h-8 rounded-lg bg-primary/15 flex items-center justify-center">
          <Sparkles size={15} className="text-[#10b981]" />
        </div>
        <div>
          <h2 className="text-foreground text-sm font-medium">JB Copilot</h2>
          <p className="text-muted-foreground text-xs">Tanyakan apa saja tentang data perusahaan</p>
        </div>
        {(user.role === "executive" || user.role === "admin") && (
          <div className="ml-auto flex items-center gap-2">
            <span className="text-muted-foreground text-xs">Cakupan:</span>
            <div className="relative">
              <select value={selectedDept} onChange={e => setSelectedDept(e.target.value)}
                className="appearance-none bg-input border border-border text-secondary-foreground text-xs rounded-lg px-3 py-1.5 pr-7 focus:outline-none focus:border-[#059669]">
                {departments.map(d => <option key={d} value={d}>{d === "all" ? "Semua Departemen" : d}</option>)}
              </select>
              <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            </div>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
              <Bot size={28} className="text-[#10b981]" />
            </div>
            <h3 className="text-foreground mb-2">Tanyakan apa saja</h3>
            <p className="text-muted-foreground text-sm max-w-sm mb-8">
              Copilot akan mencari di knowledge base{" "}
              {user.role === "executive" || user.role === "admin" ? "seluruh departemen" : `${user.department}`}{" "}
              dan memberikan jawaban dengan referensi sumber.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
              {(user.role === "executive" || user.role === "admin" ? SUGGESTIONS : [...SUGGESTIONS.slice(0, 2), ...CROSS_DEPT_SUGGESTIONS.slice(0, 2)]).map(s => (
                <button key={s} onClick={() => sendMessage(s)}
                  className="text-left px-4 py-3 bg-card border border-border hover:border-border rounded-xl text-secondary-foreground text-sm transition-all">
                  {s}
                </button>
              ))}
            </div>
            {user.role !== "executive" && user.role !== "admin" && chatbotSettings.restrictCrossDept && (
              <p className="text-muted-foreground text-[11px] mt-4 flex items-center gap-1.5">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#8b949e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
                Pertanyaan lintas departemen akan diblokir oleh sistem
              </p>
            )}
          </div>
        )}

        {messages.map(msg => {
          const isAssistant = msg.role === "assistant";
          const showsStructuredData = isAssistant && msg.isComplete && !msg.blocked && !msg.error && hasStructuredData(msg.content);
          // Default to "visual" when structured data is detected (Requirement 3.4)
          const currentViewMode = showsStructuredData
            ? (visualViewModes[msg.id] ?? "visual")
            : "text";

          return (
          <div key={msg.id} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "assistant" && (
              <div className="w-7 h-7 rounded-lg bg-primary/15 flex items-center justify-center shrink-0 mt-0.5">
                <Bot size={14} className="text-[#10b981]" />
              </div>
            )}
            <div className={`max-w-2xl ${msg.role === "user" ? "w-auto" : "w-full"}`}>
              {msg.role === "user" ? (
                <div className="bg-[#059669] rounded-2xl rounded-tr-sm px-4 py-2.5 text-white text-sm">
                  {msg.content}
                </div>
              ) : (
                <div className="bg-card border border-border rounded-2xl rounded-tl-sm p-4">
                  {/* Text/Visual toggle for messages with detected structured data */}
                  {showsStructuredData && (
                    <div className="flex gap-1 mb-3">
                      <button
                        onClick={() => setVisualViewModes(prev => ({ ...prev, [msg.id]: "visual" }))}
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs transition-all ${
                          currentViewMode === "visual"
                            ? "bg-[#059669] text-white"
                            : "bg-input text-muted-foreground hover:text-secondary-foreground"
                        }`}
                      >
                        <Eye size={11} />Visual
                      </button>
                      <button
                        onClick={() => setVisualViewModes(prev => ({ ...prev, [msg.id]: "text" }))}
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs transition-all ${
                          currentViewMode === "text"
                            ? "bg-[#059669] text-white"
                            : "bg-input text-muted-foreground hover:text-secondary-foreground"
                        }`}
                      >
                        <Type size={11} />Text
                      </button>
                    </div>
                  )}

                  {/* Show VisualizationTransform in visual mode, otherwise standard ResponseView */}
                  {showsStructuredData && currentViewMode === "visual" ? (
                    <div>
                      <VisualizationTransform text={msg.content} />
                      {/* Sources, metadata, suggestions still rendered from ResponseView in visual mode */}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-border">
                          <div className="text-muted-foreground text-xs mb-1.5 flex items-center gap-1">
                            <FileText size={12} /> Sumber referensi
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {msg.sources.map((s, i) => (
                              <button key={i} onClick={() => handleSourceClick(s)}
                                className="flex items-center gap-1.5 bg-secondary border border-border rounded-lg px-2.5 py-1 hover:border-primary/40 transition-colors text-left cursor-pointer">
                                <span className="text-primary text-[10px] font-medium">[{i + 1}]</span>
                                <span className="text-secondary-foreground text-[11px]">{s.title}</span>
                                <span className="text-muted-foreground text-[10px]">· {s.dept}{s.page ? ` hal.${s.page}` : ""}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                      {msg.metadata && msg.isComplete && (
                        <div className="flex items-center gap-3 text-[10px] text-muted-foreground pt-2 mt-2 border-t border-border">
                          {msg.metadata.queryTimeMs > 0 && <span>{msg.metadata.queryTimeMs}ms</span>}
                          {msg.metadata.documentsRetrieved > 0 && <span>{msg.metadata.documentsRetrieved} dokumen</span>}
                          {msg.metadata.retrievalMode && <span className="capitalize">{msg.metadata.retrievalMode}</span>}
                        </div>
                      )}
                      {msg.suggestions && msg.suggestions.length > 0 && msg.isComplete && (
                        <div className="pt-3 mt-2 space-y-1.5 border-t border-border">
                          <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                            <Sparkles className="size-3" />
                            <span>Pertanyaan lanjutan</span>
                          </div>
                          <div className="flex flex-col gap-1">
                            {msg.suggestions.map((suggestion, idx) => (
                              <button
                                key={idx}
                                onClick={() => handleSuggestionClick(suggestion)}
                                className="text-left text-xs px-2.5 py-1.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-muted hover:border-primary/30 transition-colors"
                              >
                                {suggestion}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <ResponseView
                      msg={msg}
                      onViewChange={changeView}
                      onSourceClick={handleSourceClick}
                      onSuggestionClick={handleSuggestionClick}
                    />
                  )}
                  <div className="flex items-center gap-2 mt-3 pt-2 border-t border-border">
                    <button className="text-muted-foreground hover:text-secondary-foreground p-1 rounded"><Copy size={12} /></button>
                    <button className="text-muted-foreground hover:text-[#10b981] p-1 rounded"><ThumbsUp size={12} /></button>
                    <button className="text-muted-foreground hover:text-[#f85149] p-1 rounded"><ThumbsDown size={12} /></button>
                    <button className="text-muted-foreground hover:text-secondary-foreground p-1 rounded ml-auto"><RefreshCw size={12} /></button>
                    <span className="text-muted-foreground text-[10px]">
                      {msg.timestamp.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
          );
        })}

        {loading && messages[messages.length - 1]?.isStreaming === undefined && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-lg bg-primary/15 flex items-center justify-center shrink-0">
              <Bot size={14} className="text-[#10b981]" />
            </div>
            <div className="bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex gap-1.5 items-center">
                <div className="w-1.5 h-1.5 bg-[#10b981] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <div className="w-1.5 h-1.5 bg-[#10b981] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <div className="w-1.5 h-1.5 bg-[#10b981] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                <span className="text-muted-foreground text-xs ml-2">Menganalisis knowledge base...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-border shrink-0">
        <div className="flex items-end gap-2 bg-card border border-border rounded-2xl px-4 py-3 focus-within:border-[rgba(5,150,105,0.4)] transition-colors">
          <button className="text-muted-foreground hover:text-secondary-foreground shrink-0 mb-0.5"><Paperclip size={16} /></button>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(input); } }}
            placeholder="Tanyakan sesuatu tentang data perusahaan..."
            rows={1}
            className="flex-1 bg-transparent text-secondary-foreground placeholder-[#8b949e] resize-none focus:outline-none text-sm leading-relaxed"
            style={{ maxHeight: "120px" }}
          />
          <button onClick={() => sendMessage(input)} disabled={!input.trim() || loading}
            className="bg-[#059669] hover:bg-[#047857] disabled:opacity-40 text-white rounded-xl p-2 shrink-0 transition-colors">
            <Send size={14} />
          </button>
        </div>
        <p className="text-muted-foreground text-[11px] text-center mt-2">
          JB Copilot dapat membuat kesalahan. Selalu verifikasi informasi penting.
        </p>
      </div>
      </div>
      <FileViewer doc={viewingSource} onClose={() => setViewingSource(null)} />
    </div>
  );
}
