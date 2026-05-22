import { useState, useEffect, useCallback, useMemo } from "react";
import type {
  IngestionJob,
  IngestionJobStatus,
  IngestionJobListParams,
  StageLog,
} from "../types/ingestion";
import { getJobs, getJobDetail } from "../api/ingestion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  FileText,
  RefreshCw,
  AlertTriangle,
  Loader2,
} from "lucide-react";

// ─── Constants ───────────────────────────────────────────────────────────────

const PIPELINE_STAGES = [
  "queued",
  "validating",
  "preprocessing",
  "chunking",
  "embedding",
  "completed",
] as const;

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "All Statuses" },
  { value: "queued", label: "Queued" },
  { value: "validating", label: "Validating" },
  { value: "preprocessing", label: "Preprocessing" },
  { value: "chunking", label: "Chunking" },
  { value: "embedding", label: "Embedding" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "validation_failed", label: "Validation Failed" },
  { value: "duplicate_exact", label: "Duplicate (Exact)" },
  { value: "duplicate_near", label: "Duplicate (Near)" },
  { value: "access_denied", label: "Access Denied" },
];

const ACTIVE_STATUSES: IngestionJobStatus[] = [
  "queued",
  "validating",
  "preprocessing",
  "chunking",
  "embedding",
];

const FAILED_STATUSES: IngestionJobStatus[] = [
  "failed",
  "validation_failed",
  "duplicate_exact",
  "duplicate_near",
  "access_denied",
];

const POLL_INTERVAL_MS = 5000;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getStatusVariant(
  status: IngestionJobStatus
): "default" | "secondary" | "destructive" | "outline" {
  if (status === "completed") return "default";
  if (FAILED_STATUSES.includes(status)) return "destructive";
  if (ACTIVE_STATUSES.includes(status)) return "secondary";
  return "outline";
}

function getStatusLabel(status: IngestionJobStatus): string {
  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString();
}

function formatDuration(startStr: string, endStr: string | null): string {
  const start = new Date(startStr).getTime();
  const end = endStr ? new Date(endStr).getTime() : Date.now();
  const diffMs = end - start;
  if (diffMs < 1000) return `${diffMs}ms`;
  if (diffMs < 60000) return `${(diffMs / 1000).toFixed(1)}s`;
  return `${(diffMs / 60000).toFixed(1)}m`;
}

function getErrorGuidance(
  errorCode: string | null,
  status: IngestionJobStatus
): string {
  if (status === "validation_failed") {
    if (errorCode?.includes("format"))
      return "Convert the file to a supported format (.txt, .md, .json, .docx, .pdf, .csv, .xlsx, .xls, .png, .jpg, .tiff).";
    if (errorCode?.includes("magic_bytes"))
      return "The file appears corrupted. Re-export or re-download the original file.";
    if (errorCode?.includes("json"))
      return "Fix the JSON syntax errors and re-upload.";
    if (errorCode?.includes("pdf"))
      return "The PDF file is corrupted. Try re-exporting from the source application.";
    return "Check the file format and content, then re-upload.";
  }
  if (status === "duplicate_exact")
    return "This file already exists in the knowledge base. No action needed unless you want to force re-ingestion.";
  if (status === "duplicate_near")
    return "A very similar document already exists. Review the existing document or contact an admin to override.";
  if (status === "access_denied")
    return "You don't have permission to ingest into this department/subfolder. Contact an administrator.";
  if (status === "failed")
    return "An unexpected error occurred during processing. Try re-uploading or contact support if the issue persists.";
  return "Review the error details and try again.";
}

// ─── Progress Indicator Component ────────────────────────────────────────────

function PipelineProgress({ currentStage }: { currentStage: string | null }) {
  const currentIndex = PIPELINE_STAGES.indexOf(
    currentStage as (typeof PIPELINE_STAGES)[number]
  );

  return (
    <div className="flex items-center gap-1">
      {PIPELINE_STAGES.map((stage, index) => {
        const isCompleted = index < currentIndex;
        const isCurrent = index === currentIndex;
        const isPending = index > currentIndex;

        return (
          <div key={stage} className="flex items-center gap-1">
            <div
              className={`h-2 w-2 rounded-full transition-colors ${
                isCompleted
                  ? "bg-green-500"
                  : isCurrent
                    ? "bg-blue-500 animate-pulse"
                    : isPending
                      ? "bg-muted"
                      : "bg-muted"
              }`}
              title={stage}
            />
            {index < PIPELINE_STAGES.length - 1 && (
              <div
                className={`h-0.5 w-3 ${
                  isCompleted ? "bg-green-500" : "bg-muted"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Job Detail Panel ────────────────────────────────────────────────────────

function JobDetailPanel({
  job,
  onClose,
}: {
  job: IngestionJob | null;
  onClose: () => void;
}) {
  const [detailedJob, setDetailedJob] = useState<IngestionJob | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!job) {
      setDetailedJob(null);
      return;
    }
    setLoading(true);
    getJobDetail(job.id)
      .then(setDetailedJob)
      .catch(() => setDetailedJob(job))
      .finally(() => setLoading(false));
  }, [job]);

  const displayJob = detailedJob || job;
  if (!displayJob) return null;

  const isError = FAILED_STATUSES.includes(displayJob.status);

  return (
    <Sheet open={!!job} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <FileText className="size-4" />
            {displayJob.fileName}
          </SheetTitle>
          <SheetDescription>
            Job ID: {displayJob.id}
          </SheetDescription>
        </SheetHeader>

        {loading ? (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <ScrollArea className="flex-1 px-4 pb-4">
            <div className="space-y-6">
              {/* Status & Info */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Status</span>
                  <Badge variant={getStatusVariant(displayJob.status)}>
                    {getStatusLabel(displayJob.status)}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Department</span>
                  <span className="text-sm font-medium">{displayJob.department}</span>
                </div>
                {displayJob.subfolder && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Subfolder</span>
                    <span className="text-sm font-medium">{displayJob.subfolder}</span>
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">File Size</span>
                  <span className="text-sm font-medium">
                    {(displayJob.fileSize / 1024).toFixed(1)} KB
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Created</span>
                  <span className="text-sm font-medium">
                    {formatDate(displayJob.createdAt)}
                  </span>
                </div>
                {displayJob.completedAt && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Completed</span>
                    <span className="text-sm font-medium">
                      {formatDate(displayJob.completedAt)}
                    </span>
                  </div>
                )}
                {displayJob.sensitivityLevel && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Sensitivity</span>
                    <Badge variant="outline">{displayJob.sensitivityLevel}</Badge>
                  </div>
                )}
              </div>

              {/* Progress for active jobs */}
              {ACTIVE_STATUSES.includes(displayJob.status) && (
                <div className="space-y-2">
                  <span className="text-sm font-medium">Pipeline Progress</span>
                  <PipelineProgress currentStage={displayJob.currentStage} />
                  <span className="text-xs text-muted-foreground">
                    Current stage: {displayJob.currentStage || "queued"}
                  </span>
                </div>
              )}

              {/* Error Details */}
              {isError && (
                <div className="space-y-2 rounded-md border border-destructive/50 bg-destructive/5 p-3">
                  <div className="flex items-center gap-2 text-destructive">
                    <AlertTriangle className="size-4" />
                    <span className="text-sm font-medium">Error Details</span>
                  </div>
                  {displayJob.errorCode && (
                    <div className="text-xs text-muted-foreground">
                      Code: <code className="font-mono">{displayJob.errorCode}</code>
                    </div>
                  )}
                  {displayJob.errorMessage && (
                    <p className="text-sm text-destructive/90">
                      {displayJob.errorMessage}
                    </p>
                  )}
                  {displayJob.failureStage && (
                    <div className="text-xs text-muted-foreground">
                      Failed at stage: {displayJob.failureStage}
                    </div>
                  )}
                  <div className="mt-2 rounded bg-muted/50 p-2">
                    <span className="text-xs font-medium">Suggested Action</span>
                    <p className="text-xs text-muted-foreground mt-1">
                      {getErrorGuidance(displayJob.errorCode, displayJob.status)}
                    </p>
                  </div>
                </div>
              )}

              {/* Stage History */}
              <div className="space-y-2">
                <span className="text-sm font-medium">Stage History</span>
                {displayJob.stages && displayJob.stages.length > 0 ? (
                  <div className="space-y-2">
                    {displayJob.stages.map((stage: StageLog, index: number) => (
                      <StageLogEntry key={index} stage={stage} />
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    No stage history available.
                  </p>
                )}
              </div>
            </div>
          </ScrollArea>
        )}
      </SheetContent>
    </Sheet>
  );
}

function StageLogEntry({ stage }: { stage: StageLog }) {
  const statusIcon =
    stage.status === "completed" ? (
      <CheckCircle2 className="size-3.5 text-green-500" />
    ) : stage.status === "failed" ? (
      <XCircle className="size-3.5 text-destructive" />
    ) : (
      <Loader2 className="size-3.5 text-blue-500 animate-spin" />
    );

  return (
    <div className="flex items-start gap-2 rounded border border-border p-2">
      <div className="mt-0.5">{statusIcon}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium capitalize">{stage.stage}</span>
          <span className="text-xs text-muted-foreground">
            {formatDuration(stage.startedAt, stage.completedAt)}
          </span>
        </div>
        <div className="text-xs text-muted-foreground">
          {formatDate(stage.startedAt)}
        </div>
        {stage.details && Object.keys(stage.details).length > 0 && (
          <div className="mt-1 text-xs text-muted-foreground font-mono bg-muted/50 rounded p-1 overflow-x-auto">
            {JSON.stringify(stage.details, null, 2)}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Dashboard Component ────────────────────────────────────────────────

export function IngestionDashboard() {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState<IngestionJob | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [departmentFilter, setDepartmentFilter] = useState<string>("all");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");

  // Fetch jobs
  const fetchJobs = useCallback(async () => {
    try {
      const params: IngestionJobListParams = {};
      if (statusFilter !== "all")
        params.status = statusFilter as IngestionJobStatus;
      if (departmentFilter !== "all") params.department = departmentFilter;
      if (dateFrom) params.dateFrom = dateFrom;
      if (dateTo) params.dateTo = dateTo;

      const response = await getJobs(params);
      setJobs(response.jobs);
      setTotal(response.total);
    } catch {
      // Keep existing data on error
    } finally {
      setLoading(false);
    }
  }, [statusFilter, departmentFilter, dateFrom, dateTo]);

  // Initial fetch and polling
  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Poll for active jobs
  useEffect(() => {
    const hasActiveJobs = jobs.some((job) =>
      ACTIVE_STATUSES.includes(job.status)
    );
    if (!hasActiveJobs) return;

    const interval = setInterval(fetchJobs, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [jobs, fetchJobs]);

  // Compute summary stats (last 24h)
  const summary = useMemo(() => {
    const now = Date.now();
    const oneDayAgo = now - 24 * 60 * 60 * 1000;

    const activeCount = jobs.filter((j) =>
      ACTIVE_STATUSES.includes(j.status)
    ).length;

    const completedCount = jobs.filter(
      (j) =>
        j.status === "completed" &&
        new Date(j.completedAt || j.updatedAt).getTime() > oneDayAgo
    ).length;

    const failedCount = jobs.filter(
      (j) =>
        FAILED_STATUSES.includes(j.status) &&
        new Date(j.updatedAt).getTime() > oneDayAgo
    ).length;

    return { activeCount, completedCount, failedCount };
  }, [jobs]);

  // Extract unique departments for filter
  const departments = useMemo(() => {
    const depts = new Set(jobs.map((j) => j.department));
    return Array.from(depts).sort();
  }, [jobs]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="border-b border-border px-4 py-3 shrink-0">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold">Ingestion Dashboard</h1>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setLoading(true);
              fetchJobs();
            }}
            disabled={loading}
          >
            <RefreshCw
              className={`size-4 mr-1 ${loading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-4">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card className="py-4">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <Activity className="size-4 text-blue-500" />
                  Active Jobs
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{summary.activeCount}</div>
                <p className="text-xs text-muted-foreground">Currently processing</p>
              </CardContent>
            </Card>

            <Card className="py-4">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <CheckCircle2 className="size-4 text-green-500" />
                  Completed (24h)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{summary.completedCount}</div>
                <p className="text-xs text-muted-foreground">Last 24 hours</p>
              </CardContent>
            </Card>

            <Card className="py-4">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <XCircle className="size-4 text-destructive" />
                  Failed (24h)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{summary.failedCount}</div>
                <p className="text-xs text-muted-foreground">Last 24 hours</p>
              </CardContent>
            </Card>
          </div>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-3">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger size="sm">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={departmentFilter} onValueChange={setDepartmentFilter}>
              <SelectTrigger size="sm">
                <SelectValue placeholder="Department" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Departments</SelectItem>
                {departments.map((dept) => (
                  <SelectItem key={dept} value={dept}>
                    {dept}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-36 h-8 text-xs"
              placeholder="From"
            />
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-36 h-8 text-xs"
              placeholder="To"
            />

            {(statusFilter !== "all" ||
              departmentFilter !== "all" ||
              dateFrom ||
              dateTo) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setStatusFilter("all");
                  setDepartmentFilter("all");
                  setDateFrom("");
                  setDateTo("");
                }}
              >
                Clear filters
              </Button>
            )}

            <span className="text-xs text-muted-foreground ml-auto">
              {total} total jobs
            </span>
          </div>

          {/* Job List Table */}
          <div className="rounded-md border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="text-left px-3 py-2 font-medium">File Name</th>
                  <th className="text-left px-3 py-2 font-medium">Department</th>
                  <th className="text-left px-3 py-2 font-medium">Status</th>
                  <th className="text-left px-3 py-2 font-medium">Progress</th>
                  <th className="text-left px-3 py-2 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {loading && jobs.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-8">
                      <Loader2 className="size-5 animate-spin mx-auto text-muted-foreground" />
                    </td>
                  </tr>
                ) : jobs.length === 0 ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="text-center py-8 text-muted-foreground"
                    >
                      No ingestion jobs found.
                    </td>
                  </tr>
                ) : (
                  jobs.map((job) => (
                    <tr
                      key={job.id}
                      className="border-b border-border last:border-0 hover:bg-muted/30 cursor-pointer transition-colors"
                      onClick={() => setSelectedJob(job)}
                    >
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          <FileText className="size-3.5 text-muted-foreground shrink-0" />
                          <span className="truncate max-w-[200px]">
                            {job.fileName}
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {job.department}
                      </td>
                      <td className="px-3 py-2">
                        <Badge variant={getStatusVariant(job.status)}>
                          {getStatusLabel(job.status)}
                        </Badge>
                      </td>
                      <td className="px-3 py-2">
                        {ACTIVE_STATUSES.includes(job.status) ? (
                          <PipelineProgress currentStage={job.currentStage} />
                        ) : job.status === "completed" ? (
                          <span className="text-xs text-green-600 flex items-center gap-1">
                            <CheckCircle2 className="size-3" />
                            Done
                          </span>
                        ) : FAILED_STATUSES.includes(job.status) ? (
                          <span className="text-xs text-destructive flex items-center gap-1">
                            <XCircle className="size-3" />
                            {job.failureStage || "Error"}
                          </span>
                        ) : (
                          <Clock className="size-3.5 text-muted-foreground" />
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">
                        {formatDate(job.createdAt)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </ScrollArea>

      {/* Job Detail Panel */}
      <JobDetailPanel
        job={selectedJob}
        onClose={() => setSelectedJob(null)}
      />
    </div>
  );
}

export default IngestionDashboard;
