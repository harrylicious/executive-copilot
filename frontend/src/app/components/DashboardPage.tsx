import { TrendingUp, FileText, MessageSquare, Users, Clock, AlertCircle } from "lucide-react";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import type { UserProfile } from "./Sidebar";
import { useDashboard } from "../../hooks/useDashboard";

const DEPT_COLORS = ["#10b981", "#f59e0b", "#8b5cf6", "#3b82f6", "#ef4444", "#ec4899"];

interface Props { user: UserProfile; onNavigate: (page: string) => void; }

function KpiCardSkeleton() {
  return (
    <div className="bg-card border border-border rounded-xl p-4 animate-pulse">
      <div className="flex items-start justify-between mb-3">
        <div className="w-9 h-9 rounded-lg bg-secondary" />
      </div>
      <div className="h-6 w-16 bg-secondary rounded mb-1" />
      <div className="h-3 w-24 bg-secondary rounded mt-1" />
    </div>
  );
}

function ChartSkeleton({ height = 180 }: { height?: number }) {
  return (
    <div className="animate-pulse">
      <div className="h-4 w-48 bg-secondary rounded mb-1" />
      <div className="h-3 w-32 bg-secondary rounded mb-4" />
      <div className="bg-secondary rounded-lg" style={{ height }} />
    </div>
  );
}

export function DashboardPage({ user, onNavigate }: Props) {
  const isExecOrAdmin = user.role === "executive" || user.role === "admin";
  const { data, loading, error, isStale, refetch } = useDashboard();

  // Error state: API failed and no cached data
  const showErrorState = error !== null && data === null && !loading;

  // Derive chart data from API response
  const deptActivity = (data?.department_distribution ?? []).map((d, i) => ({
    name: d.department,
    value: d.query_count,
    color: DEPT_COLORS[i % DEPT_COLORS.length],
  }));

  const queryTrend = (data?.query_trend ?? []).map(t => ({
    date: t.date,
    count: t.count,
  }));

  const recentActivities = data?.recent_activities ?? [];

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-foreground mb-1">Selamat datang, {user.name.split(" ")[0]} 👋</h1>
        <p className="text-muted-foreground text-sm">
          {isExecOrAdmin
            ? "Ringkasan aktivitas seluruh departemen hari ini."
            : `Ringkasan aktivitas departemen ${user.department} Anda.`}
        </p>
      </div>

      {/* Stale data warning banner */}
      {isStale && (
        <div className="flex items-center gap-2 p-3 mb-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg" role="alert">
          <AlertCircle size={16} className="text-yellow-500 shrink-0" />
          <span className="text-yellow-500 text-sm">Data mungkin sudah tidak terbaru karena gagal memperbarui</span>
        </div>
      )}

      {/* Error state: no data available */}
      {showErrorState && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <AlertCircle size={40} className="text-destructive mb-4" />
          <h2 className="text-foreground text-lg mb-1">Data tidak tersedia</h2>
          <p className="text-muted-foreground text-sm mb-4">{error}</p>
          <button
            onClick={refetch}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm hover:opacity-90 transition-opacity"
          >
            Coba Lagi
          </button>
        </div>
      )}

      {/* KPI cards */}
      {!showErrorState && loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <KpiCardSkeleton key={i} />
          ))}
        </div>
      ) : !showErrorState ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[
            { label: "Total Dokumen", value: data?.kpi.total_documents?.toLocaleString() ?? "0", icon: FileText, color: "#10b981" },
            { label: "Query Hari Ini", value: data?.kpi.total_queries_today?.toLocaleString() ?? "0", icon: MessageSquare, color: "#10b981" },
            { label: isExecOrAdmin ? "Departemen Aktif" : "Anggota Tim", value: data?.kpi.active_departments?.toLocaleString() ?? "0", icon: Users, color: "#f59e0b" },
            { label: "Akurasi AI", value: data ? `${data.kpi.ai_accuracy}%` : "0%", icon: TrendingUp, color: "#8b5cf6" },
          ].map(kpi => (
            <div key={kpi.label} className="bg-card border border-border rounded-xl p-4">
              <div className="flex items-start justify-between mb-3">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: `${kpi.color}18` }}>
                  <kpi.icon size={16} style={{ color: kpi.color }} />
                </div>
              </div>
              <div className="text-foreground text-xl font-light">{kpi.value}</div>
              <div className="text-muted-foreground text-xs mt-0.5">{kpi.label}</div>
            </div>
          ))}
        </div>
      ) : null}

      {!showErrorState && loading ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
          <div className="lg:col-span-2 bg-card border border-border rounded-xl p-4">
            <ChartSkeleton height={180} />
          </div>
          <div className="bg-card border border-border rounded-xl p-4">
            <ChartSkeleton height={160} />
          </div>
        </div>
      ) : !showErrorState ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
          {/* Department query distribution bar chart */}
          <div className="lg:col-span-2 bg-card border border-border rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-foreground text-sm">Request/Query per Department</h3>
                <p className="text-muted-foreground text-xs">Distribusi query per departemen</p>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={deptActivity} barGap={4}>
                <XAxis dataKey="name" tick={{ fill: "#8b949e", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#8b949e", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "#1c2333", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px", color: "#e6edf3", fontSize: 12 }} />
                <Bar dataKey="value" fill="#059669" radius={[4, 4, 0, 0]} name="Queries" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Dept activity pie (exec/admin) */}
          {isExecOrAdmin && (
            <div className="bg-card border border-border rounded-xl p-4">
              <h3 className="text-foreground text-sm mb-1">Aktivitas per Departemen</h3>
              <p className="text-muted-foreground text-xs mb-4">% query minggu ini</p>
              <ResponsiveContainer width="100%" height={120}>
                <PieChart>
                  <Pie data={deptActivity} cx="50%" cy="50%" innerRadius={35} outerRadius={55} dataKey="value" strokeWidth={0}>
                    {deptActivity.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#1c2333", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px", color: "#e6edf3", fontSize: 11 }} formatter={(v) => [`${v}`]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5 mt-2">
                {deptActivity.map(d => (
                  <div key={d.name} className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full shrink-0" style={{ background: d.color }} />
                    <span className="text-muted-foreground text-xs flex-1">{d.name}</span>
                    <span className="text-secondary-foreground text-xs">{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Query trend line chart (staff) */}
          {!isExecOrAdmin && (
            <div className="bg-card border border-border rounded-xl p-4">
              <h3 className="text-foreground text-sm mb-1">Query Harian</h3>
              <p className="text-muted-foreground text-xs mb-4">Tren Query</p>
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={queryTrend}>
                  <XAxis dataKey="date" tick={{ fill: "#8b949e", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#8b949e", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: "#1c2333", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px", color: "#e6edf3", fontSize: 12 }} />
                  <Line type="monotone" dataKey="count" stroke="#10b981" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      ) : null}

      {/* Recent activity */}
      {!showErrorState && (
      <div className="bg-card border border-border rounded-xl p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-foreground text-sm">Aktivitas Terbaru</h3>
          <button className="text-[#10b981] text-xs hover:underline">Lihat semua</button>
        </div>
        <div className="space-y-2">
          {recentActivities.map((a, i) => (
            <div key={i} className="flex items-center gap-3 py-2 border-b border-border last:border-0">
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${a.activity_type === "upload" ? "bg-[rgba(59,130,246,0.1)]" : "bg-[rgba(16,185,129,0.1)]"}`}>
                {a.activity_type === "upload" ? <FileText size={12} className="text-[#10b981]" /> : <MessageSquare size={12} className="text-[#10b981]" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-secondary-foreground text-xs truncate">{a.description}</div>
                <div className="text-muted-foreground text-[11px]">{a.department}</div>
              </div>
              <div className="flex items-center gap-1 text-muted-foreground text-[11px] shrink-0">
                <Clock size={10} />
                {a.timestamp}
              </div>
            </div>
          ))}
        </div>
      </div>
      )}

      {/* Quick actions */}
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        <button onClick={() => onNavigate("chat")}
          className="flex items-center gap-3 p-4 bg-secondary border border-border rounded-xl hover:border-border transition-all text-left">
          <div className="w-9 h-9 rounded-lg bg-[rgba(5,150,105,0.2)] flex items-center justify-center">
            <MessageSquare size={16} className="text-[#10b981]" />
          </div>
          <div>
            <div className="text-secondary-foreground text-sm">Mulai Chat</div>
            <div className="text-muted-foreground text-xs">Tanyakan sesuatu ke Copilot</div>
          </div>
        </button>
        <button onClick={() => onNavigate("knowledge")}
          className="flex items-center gap-3 p-4 bg-card border border-border rounded-xl hover:border-border transition-all text-left">
          <div className="w-9 h-9 rounded-lg bg-[rgba(16,185,129,0.1)] flex items-center justify-center">
            <FileText size={16} className="text-[#10b981]" />
          </div>
          <div>
            <div className="text-secondary-foreground text-sm">Unggah Dokumen</div>
            <div className="text-muted-foreground text-xs">Tambah ke knowledge base</div>
          </div>
        </button>
      </div>
    </div>
  );
}
