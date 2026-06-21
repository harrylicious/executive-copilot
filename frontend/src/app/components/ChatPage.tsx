import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import {
  Send, BarChart2, Table, AlignLeft, Copy, ThumbsUp,
  ThumbsDown, RefreshCw, Bot, ChevronDown, Sparkles, LayoutList, PanelLeft, Plus,
  Loader2, FileText, AlertCircle, Eye, Type, TrendingUp, CircleDot, X, Settings, FolderOpen, Layers, Search as SearchIcon
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } from "recharts";
import { marked } from "marked";
import { toast } from "sonner";
import type { UserProfile } from "./Sidebar";
import type { ChatbotSettings } from "../App";
import { FileViewer } from "./FileViewer";
import { streamChat, type ChatStreamEvent } from "../../api/chat";
import { transformContent, type TransformFormat } from "../../api/transform";
import { submitFeedback, getSessionFeedback } from "../../api/feedback";
import { getSession, saveSession } from "../../api/kb";
import { SessionList } from "./SessionList";
import {
  Tooltip as ShadTooltip,
  TooltipTrigger as ShadTooltipTrigger,
  TooltipContent as ShadTooltipContent,
} from "./ui/tooltip";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "./ui/popover";
import { VisualizationTransform } from "./chatplayground/VisualizationTransform";
import { TestedQuestionsBrowser } from "./TestedQuestionsBrowser";
import { detectMarkdownTable, detectNumericData, detectList } from "../../utils/visualizationDetector";
import {
  ALL_TESTED_QUESTIONS,
  GENERAL_SUGGESTIONS,
  CROSS_DEPT_SUGGESTIONS as CROSS_DEPT_DATA,
} from "../data/testedQuestions";

// Configure marked
marked.setOptions({ breaks: true, gfm: true });

/** Fallback UUID generator for non-secure contexts (HTTP over LAN). */
function generateFallbackUUID(): string {
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) => {
    const n = Number(c);
    return (n ^ (Math.random() * 16 >> (n / 4))).toString(16);
  });
}

/* ---------- types ---------- */

interface Source {
  title: string;
  dept: string;
  page?: number;
  fileId?: number;
  chunkIndex?: number;
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

interface Props { user: UserProfile; chatbotSettings: ChatbotSettings; onChatbotSettingsChange?: (settings: ChatbotSettings) => void; onNavigate?: (page: string) => void; }

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

/* ── Shared meta sections (sources, metadata, suggestions) ── */

interface ResponseMetaProps {
  sources?: Source[];
  metadata?: RetrievalMeta;
  suggestions?: string[];
  isComplete?: boolean;
  onSourceClick: (source: Source) => void;
  onSuggestionClick: (text: string) => void;
}

function ResponseMeta({ sources, metadata, suggestions, isComplete, onSourceClick, onSuggestionClick }: ResponseMetaProps) {
  return (
    <>
      {/* Sources */}
      {sources && sources.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border/60">
          <div className="text-muted-foreground text-[11px] mb-2 flex items-center gap-1.5 font-medium">
            <FileText size={12} />
            <span>Sumber referensi</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {sources.map((s, i) => (
              <button key={i} onClick={() => onSourceClick(s)}
                className="group flex items-center gap-1.5 bg-secondary/50 hover:bg-secondary border border-border/60 hover:border-primary/30 rounded-lg px-2.5 py-1.5 transition-all cursor-pointer">
                <span className="text-primary text-[10px] font-semibold tabular-nums">[{i + 1}]</span>
                <span className="text-secondary-foreground text-[12px] group-hover:text-foreground transition-colors">{s.title}</span>
                <span className="text-muted-foreground text-[10px]">· {s.dept}{s.page ? ` hal.${s.page}` : ""}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Metadata */}
      {metadata && isComplete && (
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground/70 pt-2 mt-2 border-t border-border/40">
          {metadata.queryTimeMs > 0 && <span className="tabular-nums">{metadata.queryTimeMs}ms</span>}
          {metadata.documentsRetrieved > 0 && <span className="tabular-nums">{metadata.documentsRetrieved} dokumen</span>}
          {metadata.retrievalMode && (
            <ShadTooltip>
              <ShadTooltipTrigger asChild>
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-secondary/40 text-[9px] uppercase tracking-wider font-medium cursor-default">
                  {metadata.retrievalMode}
                </span>
              </ShadTooltipTrigger>
              <ShadTooltipContent side="top" align="center" className="max-w-52">
                <p className="text-[10px] leading-relaxed">
                  {metadata.retrievalMode === "combined"
                    ? "Menggabungkan pencarian lokal (dokumen) dan global (ringkasan komunitas) untuk hasil yang lebih komprehensif."
                    : metadata.retrievalMode === "local"
                      ? "Mencari jawaban dari potongan-potongan dokumen spesifik."
                      : "Mencari jawaban dari ringkasan komunitas pengetahuan yang lebih luas."}
                </p>
              </ShadTooltipContent>
            </ShadTooltip>
          )}
        </div>
      )}

      {/* Follow-up suggestions */}
      {suggestions && suggestions.length > 0 && isComplete && (
        <div className="pt-3 mt-2 space-y-1.5 border-t border-border/60">
          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground font-medium">
            <Sparkles className="size-3" />
            <span>Pertanyaan lanjutan</span>
          </div>
          <div className="flex flex-col gap-1">
            {suggestions.map((suggestion, idx) => (
              <button
                key={idx}
                onClick={() => onSuggestionClick(suggestion)}
                className="group text-left text-[12px] px-3 py-1.5 rounded-lg border border-border/50 text-muted-foreground hover:text-foreground hover:bg-secondary/60 hover:border-primary/20 transition-all"
              >
                <span className="inline-block mr-1.5 text-primary/50 group-hover:text-primary/80 transition-colors">↳</span>
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      )}
    </>
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
        <div className="flex items-start gap-3 mb-3 p-3.5 bg-[rgba(248,81,73,0.06)] border border-[rgba(248,81,73,0.15)] rounded-xl">
          <div className="w-7 h-7 rounded-lg bg-[rgba(248,81,73,0.12)] flex items-center justify-center shrink-0 mt-0.5">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f85149" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
          </div>
          <div>
            <div className="text-[#f85149] text-[11px] font-semibold mb-1 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#f85149]" />
              Akses Dibatasi
            </div>
            <div className="text-secondary-foreground text-sm leading-relaxed whitespace-pre-line">{msg.content}</div>
          </div>
        </div>
      )}

      {/* Error state */}
      {msg.error && (
        <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-destructive/8 border border-destructive/15">
          <div className="w-6 h-6 rounded-lg bg-destructive/10 flex items-center justify-center shrink-0">
            <AlertCircle className="size-3.5 text-destructive" />
          </div>
          <span className="text-xs text-destructive font-medium">{msg.error}</span>
        </div>
      )}

      {/* View toggle (mock table/chart only) */}
      {!msg.blocked && !msg.error && (hasTable || hasChart) && (
        <div className="flex gap-1 mb-3 p-0.5 bg-secondary/40 rounded-lg w-fit border border-border/40">
          {(["text", "table", "chart"] as const).filter(v => v === "text" || (v === "table" && hasTable) || (v === "chart" && hasChart)).map(v => (
            <button key={v} onClick={() => onViewChange(msg.id, v)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                view === v
                  ? "bg-card text-foreground shadow-sm border border-border/50"
                  : "text-muted-foreground hover:text-secondary-foreground"
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
          <div className="flex gap-1 p-0.5 bg-secondary/40 rounded-lg w-fit border border-border/40 mb-3">
            {(["bar", "line", "pie", "stacked"] as const).filter(t => {
              if (t === "stacked") return msg.tableData && Object.keys(msg.tableData[0]).length > 2;
              return true;
            }).map(ct => (
              <button key={ct} onClick={() => onViewChange(msg.id, "chart", ct)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                  (msg.chartType || "bar") === ct
                    ? "bg-card text-foreground shadow-sm border border-border/50"
                    : "text-muted-foreground hover:text-secondary-foreground"
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

      {/* Sources / Metadata / Suggestions (shared component) */}
      {!msg.blocked && (
        <ResponseMeta
          sources={view === "text" ? msg.sources : undefined}
          metadata={msg.metadata}
          suggestions={view === "text" ? msg.suggestions : undefined}
          isComplete={msg.isComplete}
          onSourceClick={onSourceClick}
          onSuggestionClick={onSuggestionClick}
        />
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

export function ChatPage({ user, chatbotSettings, onChatbotSettingsChange, onNavigate }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedDept, setSelectedDept] = useState(user.role === "executive" || user.role === "admin" ? "all" : user.department);
  const [viewingSource, setViewingSource] = useState<{
    id: string; name: string; type: string; size: string; dept: string;
    uploadedBy: string; uploadedAt: string; pages?: number; chunks?: number; status?: string;
  } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef<string>(self.crypto?.randomUUID?.() ?? generateFallbackUUID());
  const titleRef = useRef<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  // Per-message view mode: "text" | "visual". Default to "visual" when structured data is detected.
  const [visualViewModes, setVisualViewModes] = useState<Record<string, "text" | "visual">>({});
  // Feedback state: track which messages have been rated
  const [feedbackMap, setFeedbackMap] = useState<Record<string, "like" | "dislike">>({});
  // Tested questions browser modal
  const [browserOpen, setBrowserOpen] = useState(false);
  // Dislike modal state
  const [dislikeModal, setDislikeModal] = useState<{ messageId: string } | null>(null);
  const [dislikeReason, setDislikeReason] = useState("");
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

  /** Open the FileViewer for a source doc from the backend. */
  const handleSourceClick = (source: Source) => {
    const sourceId = source.fileId ? String(source.fileId) : Date.now().toString();
    setViewingSource({
      id: sourceId,
      name: source.title,
      dept: source.dept,
      type: source.title.split(".").pop()?.toLowerCase() || "txt",
      size: "—",
      uploadedBy: "—",
      uploadedAt: "—",
      pages: source.page,
      chunks: source.chunkIndex,
    });
  };

  /** Click a follow-up suggestion  */
  const handleSuggestionClick = (text: string) => {
    sendMessage(text);
  };

  /** Transform an assistant response into a different format (table, chart, etc.) */
  const handleTransform = async (sourceMsg: Message, format: TransformFormat) => {
    if (loading) return;

    const transformLabel = format === "table" ? "📊 Tampilkan sebagai Tabel"
      : format === "bar" ? "📊 Tampilkan sebagai Bar Chart"
      : format === "line" ? "📈 Tampilkan sebagai Line Chart"
      : format === "pie" ? "🥧 Tampilkan sebagai Pie Chart"
      : "🍩 Tampilkan sebagai Donut Chart";

    // Show a user message indicating the transform request
    const userMsg: Message = { id: Date.now().toString(), role: "user", content: transformLabel, timestamp: new Date() };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    const assistantId = (Date.now() + 1).toString();

    try {
      const result = await transformContent({
        content: sourceMsg.content,
        format,
        language: chatbotSettings.language,
      });

      const assistantMsg: Message = {
        id: assistantId, role: "assistant", content: result.transformed,
        timestamp: new Date(), isComplete: true, isStreaming: false,
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch {
      const errorMsg: Message = {
        id: assistantId, role: "assistant",
        content: "Gagal mengubah format. Silakan coba lagi.",
        timestamp: new Date(), isComplete: true, isStreaming: false,
        error: "Transform failed",
      };
      setMessages(prev => [...prev, errorMsg]);
    }

    setMessages(prev => {
      persistCurrentSession(prev);
      return prev;
    });
    setLoading(false);
  };

  /** Handle like button click */
  const handleLike = async (msgId: string) => {
    setFeedbackMap(prev => ({ ...prev, [msgId]: "like" }));
    try {
      await submitFeedback({ message_id: msgId, session_id: sessionIdRef.current, rating: "like" });
      toast.success("Terima kasih atas feedback Anda!");
    } catch {
      toast.error("Gagal menyimpan feedback");
    }
  };

  /** Handle dislike button click — open modal for reason */
  const handleDislike = (msgId: string) => {
    setDislikeModal({ messageId: msgId });
    setDislikeReason("");
  };

  /** Submit dislike with reason from modal */
  const handleDislikeSubmit = async () => {
    if (!dislikeModal) return;
    const { messageId } = dislikeModal;
    setFeedbackMap(prev => ({ ...prev, [messageId]: "dislike" }));
    setDislikeModal(null);
    try {
      await submitFeedback({
        message_id: messageId,
        session_id: sessionIdRef.current,
        rating: "dislike",
        reason: dislikeReason.trim() || undefined,
      });
      toast.success("Feedback disimpan. Terima kasih!");
    } catch {
      toast.error("Gagal menyimpan feedback");
    }
    setDislikeReason("");
  };

  /** Regenerate an assistant response by re-sending the preceding user query */
  const handleRegenerate = async (assistantMsgId: string) => {
    if (loading) return;

    // Find the index of this assistant message
    const msgIndex = messages.findIndex(m => m.id === assistantMsgId);
    if (msgIndex < 0) return;

    // Find the preceding user message
    let userQuery = "";
    for (let i = msgIndex - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        userQuery = messages[i].content;
        break;
      }
    }
    if (!userQuery) return;

    // Remove the old assistant message
    setMessages(prev => prev.filter(m => m.id !== assistantMsgId));
    setLoading(true);

    // Create a new empty assistant message for streaming
    const newAssistantId = Date.now().toString();
    const emptyMsg: Message = {
      id: newAssistantId, role: "assistant", content: "", timestamp: new Date(),
      sources: [], suggestions: [], isStreaming: true, isComplete: false,
    };
    setMessages(prev => [...prev, emptyMsg]);

    try {
      await streamChat(
        { query: userQuery, language: chatbotSettings.language },
        (evt: ChatStreamEvent) => {
          switch (evt.event) {
            case "token":
              setMessages(prev => prev.map(m =>
                m.id === newAssistantId ? { ...m, content: m.content + (evt.data as { content: string }).content } : m
              ));
              break;
            case "sources":
              setMessages(prev => prev.map(m =>
                m.id === newAssistantId ? {
                  ...m,
                  sources: (evt.data as { source_attributions: Array<{ file_id: number; file_name: string; department: string; chunk_index: number }> }).source_attributions.map(s => ({
                    title: s.file_name, dept: s.department, fileId: s.file_id, chunkIndex: s.chunk_index,
                  })),
                } : m
              ));
              break;
            case "metadata":
              setMessages(prev => prev.map(m =>
                m.id === newAssistantId ? {
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
                m.id === newAssistantId ? { ...m, suggestions: (evt.data as { suggestions: string[] }).suggestions } : m
              ));
              break;
            case "done":
              setMessages(prev => prev.map(m =>
                m.id === newAssistantId ? { ...m, isStreaming: false, isComplete: true } : m
              ));
              break;
            case "error":
              setMessages(prev => prev.map(m =>
                m.id === newAssistantId ? { ...m, error: (evt.data as { message: string }).message, isStreaming: false } : m
              ));
              break;
          }
        }
      );
    } catch {
      setMessages(prev => prev.map(m =>
        m.id === newAssistantId ? { ...m, content: "Gagal membuat ulang jawaban. Silakan coba lagi.", error: "Regenerate failed", isStreaming: false, isComplete: true } : m
      ));
    }

    setMessages(prev => {
      persistCurrentSession(prev);
      return prev;
    });
    setLoading(false);
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
        { query: text, session_id: sessionIdRef.current, language: chatbotSettings.language, nuance: chatbotSettings.nuance },
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
                  sources: (evt.data as { source_attributions: Array<{ file_id: number; file_name: string; department: string; chunk_index: number }> }).source_attributions.map(s => ({
                    title: s.file_name, dept: s.department, fileId: s.file_id, chunkIndex: s.chunk_index,
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
      const isEnglish = chatbotSettings.language === "en";
      const scope = selectedDept === "all"
        ? (isEnglish ? "all departments" : "seluruh departemen")
        : (isEnglish ? `department ${selectedDept}` : `departemen ${selectedDept}`);
      const greeting = NUANCE_PROMPTS[chatbotSettings.nuance][chatbotSettings.language];
      const body = isEnglish
        ? `Based on the analysis of **${scope}**, here is a summary of sales data by region:\n\n• **DKI Jakarta** leads with a total of **4,140 million IDR** (Q1 2024)\n• **West Java** is second with **2,860 million IDR**\n• **Highest growth** in East Java (+24% MoM)`
        : `Berdasarkan analisis dari **${scope}**, berikut ringkasan data penjualan per wilayah:\n\n• **DKI Jakarta** memimpin dengan total **4.140 juta IDR** (Q1 2024)\n• **Jawa Barat** di posisi kedua dengan **2.860 juta IDR**\n• **Pertumbuhan tertinggi** di Jawa Timur (+24% MoM)`;
      const suggestions = isEnglish
        ? ["Show data as table", "Compare with Q1 2024", "Which region needs improvement?"]
        : ["Tampilkan data dalam bentuk tabel", "Bandingkan dengan Q1 2024", "Wilayah mana yang perlu perbaikan?"];
      const fallbackMsg: Message = {
        id: assistantId, role: "assistant", timestamp: new Date(),
        content: `${greeting}\n\n${body}`,
        sources: isEnglish
          ? [
              { title: "Sales Report Q2 2024.xlsx", dept: "Demand Supply", page: 3 },
              { title: "Monthly Performance Review.pdf", dept: "Demand Supply", page: 7 },
            ]
          : [
              { title: "Laporan Penjualan Q2 2024.xlsx", dept: "Demand Supply", page: 3 },
              { title: "Review Kinerja Bulanan.pdf", dept: "Demand Supply", page: 7 },
            ],
        suggestions,
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
    sessionIdRef.current = self.crypto?.randomUUID?.() ?? generateFallbackUUID();
    titleRef.current = null;
    sessionCreatedRef.current = false;
    pendingQueueRef.current.clear();
    setMessages([]);
    setFeedbackMap({});
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
          ? record.sources.map((s) => ({ title: s.fileName, dept: s.department, page: s.chunkIndex, fileId: s.fileId, chunkIndex: s.chunkIndex }))
          : undefined,
        metadata: record.metadataJson ?? undefined,
        error: record.error ?? undefined,
        isComplete: true,
        isStreaming: false,
      }));
      setMessages(loaded);

      // Load feedback history for this session
      try {
        const feedbacks = await getSessionFeedback(session.id);
        const map: Record<string, "like" | "dislike"> = {};
        for (const fb of feedbacks) {
          map[fb.message_id] = fb.rating;
        }
        setFeedbackMap(map);
      } catch {
        // Non-critical: feedback display is optional
        setFeedbackMap({});
      }
    } catch (err) {
      console.error("Failed to load session:", err);
    }
  };

  // Computed: which tested questions to show in the welcome screen based on role
  const displayQuestions = user.role === "executive" || user.role === "admin"
    ? ALL_TESTED_QUESTIONS
    : [...GENERAL_SUGGESTIONS.slice(0, 6), ...CROSS_DEPT_DATA.slice(0, 4)];

  return (
    <div className="flex h-full">
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
      <div className="px-5 py-3 border-b border-border/80 flex items-center gap-3 shrink-0 bg-card/30 backdrop-blur-sm">
        {!sidebarOpen && (
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-all mr-1"
            title="Buka riwayat chat"
          >
            <PanelLeft className="size-4" />
          </button>
        )}
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#10b981] to-[#059669] shadow-lg shadow-[#059669]/20 flex items-center justify-center shrink-0">
          <Sparkles size={14} className="text-white" />
        </div>
        <div>
          <h2 className="text-foreground text-sm font-semibold tracking-tight">JB Copilot</h2>
          <p className="text-muted-foreground text-[11px]">Asisten data perusahaan Anda</p>
        </div>
        <div className="flex items-center gap-1.5 ml-auto">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-secondary/70 border border-border/60 text-[10px] text-muted-foreground font-medium">
            <Type size={9} />
            {chatbotSettings.nuance.charAt(0).toUpperCase() + chatbotSettings.nuance.slice(1)}
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-secondary/70 border border-border/60 text-[10px] text-muted-foreground">
            {chatbotSettings.language === "id" ? "🇮🇩 Indonesia" : "🇬🇧 English"}
          </span>
          {(user.role === "executive" || user.role === "admin") && (
            <div className="flex items-center gap-1.5 ml-1 pl-2 border-l border-border/50">
              <span className="text-muted-foreground text-[10px] font-medium">Cakupan:</span>
              <div className="relative">
                <select value={selectedDept} onChange={e => setSelectedDept(e.target.value)}
                  className="appearance-none bg-secondary/70 border border-border/60 text-secondary-foreground text-[11px] rounded-lg px-2.5 py-1 pr-6 focus:outline-none focus:border-[#059669]/50 transition-colors cursor-pointer">
                  {departments.map(d => <option key={d} value={d}>{d === "all" ? "Semua Departemen" : d}</option>)}
                </select>
                <ChevronDown size={10} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
              </div>
            </div>
          )}
          <Popover>
            <PopoverTrigger asChild>
              <button
                className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-secondary-foreground transition-colors"
                title="Konfigurasi chatbot"
              >
                <Settings size={13} />
              </button>
            </PopoverTrigger>
            <PopoverContent align="end" sideOffset={6} className="w-56 p-3">
              <div className="space-y-3">
                <div>
                  <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider block mb-1.5">Bahasa</label>
                  <div className="flex gap-1 p-0.5 bg-secondary/40 rounded-lg border border-border/40">
                    <button
                      onClick={() => onChatbotSettingsChange?.({ ...chatbotSettings, language: "id" })}
                      className={`flex-1 text-[11px] py-1 rounded-md font-medium transition-all ${
                        chatbotSettings.language === "id"
                          ? "bg-card text-foreground shadow-sm border border-border/50"
                          : "text-muted-foreground hover:text-secondary-foreground"
                      }`}
                    >
                      🇮🇩 Indonesia
                    </button>
                    <button
                      onClick={() => onChatbotSettingsChange?.({ ...chatbotSettings, language: "en" })}
                      className={`flex-1 text-[11px] py-1 rounded-md font-medium transition-all ${
                        chatbotSettings.language === "en"
                          ? "bg-card text-foreground shadow-sm border border-border/50"
                          : "text-muted-foreground hover:text-secondary-foreground"
                      }`}
                    >
                      🇬🇧 English
                    </button>
                  </div>
                </div>
                <div>
                  <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider block mb-1.5">Nada</label>
                  <div className="space-y-0.5">
                    {(["formal", "santai", "profesional", "ramah", "tegas"] as const).map((n) => (
                      <button
                        key={n}
                        onClick={() => onChatbotSettingsChange?.({ ...chatbotSettings, nuance: n })}
                        className={`w-full text-left text-[11px] px-2.5 py-1.5 rounded-lg font-medium transition-all ${
                          chatbotSettings.nuance === n
                            ? "bg-card text-foreground shadow-sm border border-border/50"
                            : "text-muted-foreground hover:text-secondary-foreground hover:bg-muted/40"
                        }`}
                      >
                        {n.charAt(0).toUpperCase() + n.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </PopoverContent>
          </Popover>
          {onNavigate && (
            <>
              <Popover>
                <PopoverTrigger asChild>
                  <button
                    className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-secondary-foreground transition-colors"
                    title="Penjelajah berkas"
                  >
                    <FolderOpen size={13} />
                  </button>
                </PopoverTrigger>
                <PopoverContent align="end" sideOffset={6} className="w-44 p-1.5">
                  <button
                    onClick={() => onNavigate("explorer")}
                    className="w-full text-left flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-all"
                  >
                    <SearchIcon size={12} />
                    File Explorer
                  </button>
                  <button
                    onClick={() => onNavigate("knowledge")}
                    className="w-full text-left flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-all"
                  >
                    <Layers size={12} />
                    Knowledge Base
                  </button>
                </PopoverContent>
              </Popover>
              <button
                onClick={() => onNavigate("dashboard")}
                className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                title="Tutup chat"
              >
                <X size={15} />
              </button>
            </>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="relative mb-6">
              <div className="absolute inset-0 bg-gradient-to-br from-[#10b981]/20 to-[#059669]/5 blur-3xl rounded-full" />
              <div className="relative w-16 h-16 rounded-2xl bg-gradient-to-br from-[#10b981] to-[#059669] shadow-xl shadow-[#059669]/25 flex items-center justify-center">
                <Bot size={30} className="text-white" />
              </div>
            </div>
            <h3 className="text-foreground text-lg font-semibold tracking-tight mb-1.5">
              {chatbotSettings.language === "en" ? "Ask anything" : "Tanyakan apa saja"}
            </h3>
            <p className="text-muted-foreground text-sm max-w-sm mb-8 leading-relaxed">
              {chatbotSettings.language === "en" ? (
                <>Copilot will search the knowledge base across{" "}
                  <span className="text-secondary-foreground font-medium">
                    {user.role === "executive" || user.role === "admin" ? "all departments" : `${user.department}`}
                  </span>{" "}
                  and provide answers with source references.</>
              ) : (
                <>Copilot akan mencari di knowledge base{" "}
                  <span className="text-secondary-foreground font-medium">
                    {user.role === "executive" || user.role === "admin" ? "seluruh departemen" : `${user.department}`}
                  </span>{" "}
                  dan memberikan jawaban dengan referensi sumber.</>
              )}
            </p>
            <div className="w-full max-w-xl max-h-[340px] overflow-y-auto space-y-1.5 custom-scrollbar px-1">
              {displayQuestions.map((q, i) => (
                <button
                  key={q.id}
                  onClick={() => sendMessage(q.question)}
                  className="group w-full text-left px-4 py-3 bg-card/80 hover:bg-card border border-border/60 hover:border-primary/30 rounded-xl text-secondary-foreground text-sm transition-all hover:shadow-sm hover:shadow-[#059669]/5 animate-fade-in-up"
                  style={{ animationDelay: `${i * 40}ms` }}
                >
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary/40 group-hover:bg-primary mr-2.5 align-middle transition-colors" />
                  {q.question}
                </button>
              ))}
            </div>
            {user.role !== "executive" && user.role !== "admin" && chatbotSettings.restrictCrossDept && (
              <p className="text-muted-foreground/60 text-[11px] mt-5 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-muted/30 border border-border/40">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="opacity-50">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
                {chatbotSettings.language === "en" ? "Cross-department queries will be blocked by the system" : "Pertanyaan lintas departemen akan diblokir oleh sistem"}
              </p>
            )}
          </div>
        )}

        {messages.map((msg, msgIdx) => {
          const isAssistant = msg.role === "assistant";
          const showsStructuredData = isAssistant && msg.isComplete && !msg.blocked && !msg.error && hasStructuredData(msg.content);
          // Default to "visual" when structured data is detected (Requirement 3.4)
          const currentViewMode = showsStructuredData
            ? (visualViewModes[msg.id] ?? "visual")
            : "text";

          return (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"} ${msg.role === "user" ? "msg-enter-user" : "msg-enter-assistant"}`}
            style={{ animationDelay: `${msgIdx * 50}ms` }}
          >
            {msg.role === "assistant" && (
              <div className="w-7 h-7 rounded-xl bg-gradient-to-br from-[#10b981] to-[#059669] shadow-sm shadow-[#059669]/20 flex items-center justify-center shrink-0 mt-1">
                <Bot size={13} className="text-white" />
              </div>
            )}
            <div className={`max-w-2xl ${msg.role === "user" ? "w-auto" : "w-full"}`}>
              {msg.role === "user" ? (
                <div className="group relative">
                  <div className="bg-gradient-to-br from-[#059669] to-[#047857] rounded-2xl rounded-tr-sm px-4 py-2.5 text-white text-sm shadow-md shadow-[#059669]/20 leading-relaxed">
                    {msg.content}
                  </div>
                  <div className="flex justify-end mt-1 pr-1">
                    <span className="text-[10px] text-muted-foreground/50 group-hover:text-muted-foreground/80 transition-colors">
                      {msg.timestamp.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="bg-card border border-border/70 rounded-2xl rounded-tl-sm shadow-sm hover:shadow-md transition-shadow duration-200">
                  <div className="p-4">
                  {/* Text/Visual toggle for messages with detected structured data */}
                  {showsStructuredData && (
                    <div className="flex gap-1 mb-3 p-0.5 bg-secondary/40 rounded-lg w-fit border border-border/40">
                      <button
                        onClick={() => setVisualViewModes(prev => ({ ...prev, [msg.id]: "visual" }))}
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                          currentViewMode === "visual"
                            ? "bg-card text-foreground shadow-sm border border-border/50"
                            : "text-muted-foreground hover:text-secondary-foreground"
                        }`}
                      >
                        <Eye size={11} />Visual
                      </button>
                      <button
                        onClick={() => setVisualViewModes(prev => ({ ...prev, [msg.id]: "text" }))}
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                          currentViewMode === "text"
                            ? "bg-card text-foreground shadow-sm border border-border/50"
                            : "text-muted-foreground hover:text-secondary-foreground"
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
                      <ResponseMeta
                        sources={msg.sources}
                        metadata={msg.metadata}
                        suggestions={msg.suggestions}
                        isComplete={msg.isComplete}
                        onSourceClick={handleSourceClick}
                        onSuggestionClick={handleSuggestionClick}
                      />
                    </div>
                  ) : (
                    <ResponseView
                      msg={msg}
                      onViewChange={changeView}
                      onSourceClick={handleSourceClick}
                      onSuggestionClick={handleSuggestionClick}
                    />
                  )}
                  <div className="flex items-center gap-1 mt-3 pt-2.5 border-t border-border/50 opacity-60 hover:opacity-100 transition-opacity">
                    <ShadTooltip>
                      <ShadTooltipTrigger asChild>
                        <button
                          onClick={() => { navigator.clipboard.writeText(msg.content); toast.success("Disalin!"); }}
                          className="text-muted-foreground hover:text-secondary-foreground hover:bg-muted/50 p-1.5 rounded-lg transition-all"
                        >
                          <Copy size={11} />
                        </button>
                      </ShadTooltipTrigger>
                      <ShadTooltipContent side="top">Salin jawaban</ShadTooltipContent>
                    </ShadTooltip>
                    <ShadTooltip>
                      <ShadTooltipTrigger asChild>
                        <button
                          onClick={() => handleLike(msg.id)}
                          className={`p-1.5 rounded-lg transition-all ${
                            feedbackMap[msg.id] === "like"
                              ? "text-[#10b981] bg-[#10b981]/10"
                              : "text-muted-foreground hover:text-[#10b981] hover:bg-[#10b981]/5"
                          }`}
                        >
                          <ThumbsUp size={11} />
                        </button>
                      </ShadTooltipTrigger>
                      <ShadTooltipContent side="top">Suka</ShadTooltipContent>
                    </ShadTooltip>
                    <ShadTooltip>
                      <ShadTooltipTrigger asChild>
                        <button
                          onClick={() => handleDislike(msg.id)}
                          className={`p-1.5 rounded-lg transition-all ${
                            feedbackMap[msg.id] === "dislike"
                              ? "text-[#f85149] bg-[#f85149]/10"
                              : "text-muted-foreground hover:text-[#f85149] hover:bg-[#f85149]/5"
                          }`}
                        >
                          <ThumbsDown size={11} />
                        </button>
                      </ShadTooltipTrigger>
                      <ShadTooltipContent side="top">Tidak suka</ShadTooltipContent>
                    </ShadTooltip>
                    <div className="w-px h-4 bg-border/50 mx-1" />
                    {msg.isComplete && !msg.blocked && !msg.error && (
                      <>
                        <ShadTooltip>
                          <ShadTooltipTrigger asChild>
                            <button onClick={() => handleTransform(msg, "table")} disabled={loading}
                              className="text-muted-foreground hover:text-[#10b981] disabled:opacity-30 p-1.5 rounded-lg transition-all"><Table size={11} /></button>
                          </ShadTooltipTrigger>
                          <ShadTooltipContent side="top">Ubah ke tabel</ShadTooltipContent>
                        </ShadTooltip>
                        <ShadTooltip>
                          <ShadTooltipTrigger asChild>
                            <button onClick={() => handleTransform(msg, "bar")} disabled={loading}
                              className="text-muted-foreground hover:text-[#10b981] disabled:opacity-30 p-1.5 rounded-lg transition-all"><BarChart2 size={11} /></button>
                          </ShadTooltipTrigger>
                          <ShadTooltipContent side="top">Ubah ke diagram batang</ShadTooltipContent>
                        </ShadTooltip>
                        <ShadTooltip>
                          <ShadTooltipTrigger asChild>
                            <button onClick={() => handleTransform(msg, "line")} disabled={loading}
                              className="text-muted-foreground hover:text-[#10b981] disabled:opacity-30 p-1.5 rounded-lg transition-all"><TrendingUp size={11} /></button>
                          </ShadTooltipTrigger>
                          <ShadTooltipContent side="top">Ubah ke diagram garis</ShadTooltipContent>
                        </ShadTooltip>
                        <ShadTooltip>
                          <ShadTooltipTrigger asChild>
                            <button onClick={() => handleTransform(msg, "pie")} disabled={loading}
                              className="text-muted-foreground hover:text-[#10b981] disabled:opacity-30 p-1.5 rounded-lg transition-all"><CircleDot size={11} /></button>
                          </ShadTooltipTrigger>
                          <ShadTooltipContent side="top">Ubah ke diagram lingkaran</ShadTooltipContent>
                        </ShadTooltip>
                        <div className="w-px h-4 bg-border/50 mx-1" />
                      </>
                    )}
                    <ShadTooltip>
                      <ShadTooltipTrigger asChild>
                        <button onClick={() => handleRegenerate(msg.id)} disabled={loading}
                          className="text-muted-foreground hover:text-secondary-foreground hover:bg-muted/50 disabled:opacity-30 p-1.5 rounded-lg transition-all"
                        >
                          <RefreshCw size={11} />
                        </button>
                      </ShadTooltipTrigger>
                      <ShadTooltipContent side="top">Buat ulang jawaban</ShadTooltipContent>
                    </ShadTooltip>
                    <span className="text-muted-foreground/50 text-[10px] ml-auto tabular-nums">
                      {msg.timestamp.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                </div>
              </div>
            )}
            </div>
          </div>
          );
        })}

        {loading && messages[messages.length - 1]?.isStreaming === undefined && (
          <div className="flex gap-3 msg-enter-assistant">
            <div className="w-7 h-7 rounded-xl bg-gradient-to-br from-[#10b981] to-[#059669] shadow-sm shadow-[#059669]/20 flex items-center justify-center shrink-0">
              <Bot size={13} className="text-white" />
            </div>
            <div className="bg-card border border-border/70 rounded-2xl rounded-tl-sm shadow-sm px-4 py-3.5">
              <div className="flex items-center gap-3">
                <div className="flex gap-1.5 items-center">
                  <div className="w-2 h-2 bg-[#10b981] rounded-full" style={{ animation: "pulse-dot 1.4s ease-in-out infinite", animationDelay: "0ms" }} />
                  <div className="w-2 h-2 bg-[#10b981] rounded-full" style={{ animation: "pulse-dot 1.4s ease-in-out infinite", animationDelay: "280ms" }} />
                  <div className="w-2 h-2 bg-[#10b981] rounded-full" style={{ animation: "pulse-dot 1.4s ease-in-out infinite", animationDelay: "560ms" }} />
                </div>
                <span className="text-muted-foreground text-xs font-medium">Menganalisis knowledge base...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-5 py-3 border-t border-border/80 shrink-0 bg-card/20 backdrop-blur-sm">
        <div className="flex items-end gap-2 bg-card border border-border/60 rounded-2xl px-4 py-3 glow-focus transition-all duration-200 shadow-sm">
          <button
            onClick={() => setBrowserOpen(true)}
            className="text-muted-foreground/60 hover:text-[#10b981] shrink-0 mb-0.5 transition-colors"
            title="Lihat contoh pertanyaan"
          >
            <Sparkles size={16} />
          </button>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(input); } }}
            placeholder="Tanyakan sesuatu tentang data perusahaan..."
            rows={1}
            className="flex-1 bg-transparent text-secondary-foreground placeholder-muted-foreground/60 resize-none focus:outline-none text-sm leading-relaxed py-0.5"
            style={{ maxHeight: "120px" }}
          />
          <button onClick={() => sendMessage(input)} disabled={!input.trim() || loading}
            className="bg-gradient-to-br from-[#059669] to-[#047857] hover:from-[#10b981] hover:to-[#059669] disabled:opacity-40 text-white rounded-xl p-2.5 shrink-0 transition-all shadow-sm shadow-[#059669]/20 hover:shadow-md hover:shadow-[#059669]/30 active:scale-95">
            <Send size={14} />
          </button>
        </div>
        <p className="text-muted-foreground/50 text-[10px] text-center mt-2 tracking-wide">
          JB Copilot dapat membuat kesalahan. Selalu verifikasi informasi penting.
        </p>
      </div>
      </div>
      <FileViewer doc={viewingSource} onClose={() => setViewingSource(null)} />

      {/* Tested Questions Browser */}
      <TestedQuestionsBrowser
        open={browserOpen}
        onClose={() => setBrowserOpen(false)}
        onSelectQuestion={sendMessage}
      />

      {/* Dislike Reason Modal */}
      {dislikeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in" onClick={() => setDislikeModal(null)}>
          <div className="bg-card border border-border/70 rounded-2xl w-full max-w-md shadow-2xl animate-fade-in-up" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b border-border/60">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-[#f85149]/10 flex items-center justify-center">
                  <ThumbsDown size={13} className="text-[#f85149]" />
                </div>
                <h3 className="text-foreground text-sm font-semibold tracking-tight">Berikan Alasan</h3>
              </div>
              <button onClick={() => setDislikeModal(null)}
                className="text-muted-foreground hover:text-foreground p-1.5 rounded-lg hover:bg-secondary transition-colors">
                <X size={15} />
              </button>
            </div>
            <div className="p-4 space-y-3">
              <p className="text-muted-foreground text-xs">Mengapa jawaban ini kurang memuaskan? (opsional)</p>
              <div className="flex flex-wrap gap-1.5">
                {["Jawaban tidak akurat", "Tidak relevan", "Terlalu panjang", "Terlalu pendek", "Data salah"].map(preset => (
                  <button key={preset} onClick={() => setDislikeReason(preset)}
                    className={`px-3 py-1.5 text-xs rounded-lg border transition-all ${
                      dislikeReason === preset
                        ? "border-[#f85149] bg-[rgba(248,81,73,0.1)] text-[#f85149] shadow-sm"
                        : "border-border/60 text-muted-foreground hover:border-[#f85149]/30 hover:text-[#f85149]/80"
                    }`}>
                    {preset}
                  </button>
                ))}
              </div>
              <textarea
                value={dislikeReason}
                onChange={e => setDislikeReason(e.target.value)}
                placeholder="Tulis alasan lainnya..."
                rows={3}
                className="w-full bg-input/50 border border-border/60 rounded-xl px-3 py-2.5 text-sm text-secondary-foreground placeholder-muted-foreground/60 resize-none focus:outline-none focus:border-[#f85149]/40 transition-colors"
              />
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-border/60">
              <button onClick={() => setDislikeModal(null)}
                className="px-4 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground rounded-lg hover:bg-secondary transition-colors">
                Batal
              </button>
              <button onClick={handleDislikeSubmit}
                className="px-4 py-1.5 text-xs font-semibold bg-gradient-to-r from-[#f85149] to-[#da3633] hover:from-[#f85149] hover:to-[#f85149] text-white rounded-lg transition-all shadow-sm shadow-[#f85149]/20 active:scale-95">
                Kirim Feedback
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
