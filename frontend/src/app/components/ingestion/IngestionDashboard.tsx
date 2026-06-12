import { useState, useEffect, useCallback } from "react";
import { RefreshCw, Loader2, XCircle, Search, Filter } from "lucide-react";
import { cn } from "../../../utils/cn";
import { getJobs } from "../../../api/ingestion";
import { FileUpload } from "./FileUpload";
import { BatchLoaderConfig } from "./BatchLoaderConfig";
import type { IngestionJob, IngestionJobStatus } from "../../../types/ingestion";

type Tab = "upload" | "jobs" | "batch";

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  failed: "bg-red-500/10 text-red-500 border-red-500/20",
  validation_failed: "bg-red-500/10 text-red-500 border-red-500/20",
  queued: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  validating: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  preprocessing: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  chunking: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  embedding: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  duplicate_exact: "bg-blue-500/10 text-blue-500 border-blue-500/20",
  duplicate_near: "bg-blue-500/10 text-blue-500 border-blue-500/20",
  access_denied: "bg-red-500/10 text-red-500 border-red-500/20",
};

function formatSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function JobCard({
  job,
  expanded,
  onToggle,
}: {
  job: IngestionJob;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/30 transition-colors"
      >
        <div
          className={cn(
            "px-2 py-0.5 rounded-full text-[10px] font-medium border whitespace-nowrap",
            STATUS_COLORS[job.status] || "bg-muted text-muted-foreground"
          )}
        >
          {job.status.replace(/_/g, " ")}
        </div>
        <span className="text-xs text-foreground truncate flex-1">{job.fileName}</span>
        <span className="text-[10px] text-muted-foreground whitespace-nowrap">{job.department}</span>
        <span className="text-[10px] text-muted-foreground whitespace-nowrap">{formatSize(job.fileSize)}</span>
        <svg
          width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          className={cn("text-muted-foreground transition-transform shrink-0", expanded && "rotate-180")}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-border pt-3 space-y-2">
          {/* Stages timeline */}
          {job.stages.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Stages</span>
              {job.stages.map((stage, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <div
                    className={cn(
                      "w-1.5 h-1.5 rounded-full shrink-0",
                      stage.status === "completed" ? "bg-emerald-500" :
                      stage.status === "failed" ? "bg-red-500" : "bg-amber-500"
                    )}
                  />
                  <span className="text-secondary-foreground capitalize">{stage.stage}</span>
                  <span className="text-muted-foreground text-[10px]">
                    {stage.status}
                  </span>
                </div>
              ))}
            </div>
          )}

          {job.errorMessage && (
            <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-red-500/10 text-xs text-red-500">
              <XCircle size={12} className="shrink-0 mt-0.5" />
              {job.errorMessage}
            </div>
          )}

          <div className="flex gap-3 text-[10px] text-muted-foreground pt-1">
            <span>Created: {new Date(job.createdAt).toLocaleDateString("id-ID", {
              day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"
            })}</span>
            {job.completedAt && (
              <span>Completed: {new Date(job.completedAt).toLocaleDateString("id-ID", {
                day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"
              })}</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function IngestionDashboard() {
  const [activeTab, setActiveTab] = useState<Tab>("upload");
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [deptFilter, setDeptFilter] = useState("");
  const [expandedJobs, setExpandedJobs] = useState<Set<string>>(new Set());
  const [total, setTotal] = useState(0);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      if (deptFilter) params.department = deptFilter;
      const res = await getJobs(params);
      setJobs(res.jobs);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, deptFilter]);

  useEffect(() => {
    if (activeTab === "jobs") fetchJobs();
  }, [activeTab, fetchJobs]);

  const toggleJob = (id: string) => {
    setExpandedJobs((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: "upload", label: "Upload" },
    { id: "jobs", label: "Jobs" },
    { id: "batch", label: "Batch Config" },
  ];

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border shrink-0">
        <h2 className="text-sm font-medium text-foreground">Ingestion Dashboard</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Upload, monitor, and configure document ingestion
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 px-6 pt-4 border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "px-4 py-2 text-xs font-medium rounded-t-lg transition-colors capitalize",
              activeTab === tab.id
                ? "bg-card text-foreground border border-border border-b-transparent -mb-px"
                : "text-muted-foreground hover:text-secondary-foreground"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {activeTab === "upload" && <FileUpload department="" />}

        {activeTab === "batch" && <BatchLoaderConfig />}

        {activeTab === "jobs" && (
          <div className="space-y-3">
            {/* Filters */}
            <div className="flex items-center gap-2">
              <div className="relative flex-1 max-w-xs">
                <Filter size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full bg-input border border-border rounded-lg pl-8 pr-3 py-1.5 text-xs text-foreground focus:outline-none focus:border-primary/40 appearance-none"
                >
                  <option value="">All statuses</option>
                  <option value="queued">Queued</option>
                  <option value="completed">Completed</option>
                  <option value="failed">Failed</option>
                  <option value="duplicate_exact">Duplicate</option>
                </select>
              </div>
              <input
                value={deptFilter}
                onChange={(e) => setDeptFilter(e.target.value)}
                placeholder="Filter by dept..."
                className="bg-input border border-border rounded-lg px-3 py-1.5 text-xs text-foreground placeholder-muted-foreground focus:outline-none focus:border-primary/40 max-w-[160px]"
              />
              <button
                onClick={fetchJobs}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-secondary-foreground hover:bg-card transition-colors"
              >
                <RefreshCw size={14} />
              </button>
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-500">
                <XCircle size={12} />
                {error}
              </div>
            )}

            {/* Loading */}
            {loading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 size={16} className="animate-spin text-muted-foreground" />
              </div>
            )}

            {/* Job list */}
            {!loading && jobs.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-8">No ingestion jobs found</p>
            )}

            {!loading && jobs.length > 0 && (
              <div className="space-y-2">
                <p className="text-[10px] text-muted-foreground">{total} total jobs</p>
                {jobs.map((job) => (
                  <JobCard
                    key={job.id}
                    job={job}
                    expanded={expandedJobs.has(job.id)}
                    onToggle={() => toggleJob(job.id)}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default IngestionDashboard;
