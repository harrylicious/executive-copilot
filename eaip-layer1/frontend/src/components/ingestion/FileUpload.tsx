import { useState, useRef, useCallback, useEffect, type FC, type DragEvent } from "react";
import { uploadBatch, getJobDetail } from "../../api/ingestion";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { IngestionJob, IngestionJobStatus } from "../../types/ingestion";

// ─── Constants ───────────────────────────────────────────────────────────────

const DEPARTMENTS: Record<string, string[]> = {
  demand_supply: ["demand_plans", "supply_plans", "deal_orders", "forecasts", "reference"],
  accounting_tax: ["invoices", "transactions", "tax_reports", "journal_entries", "policies"],
  logistic: ["inbound", "outbound", "warehouse", "shipping_docs", "sops"],
  finance: ["cashflow", "payments", "receivables", "budgets", "reports"],
};

const DEPARTMENT_LABELS: Record<string, string> = {
  demand_supply: "Demand-Supply Planning",
  accounting_tax: "Controller Accounting Tax",
  logistic: "Logistic",
  finance: "Finance",
};

const PIPELINE_STAGES: IngestionJobStatus[] = [
  "queued",
  "validating",
  "preprocessing",
  "chunking",
  "embedding",
  "completed",
];

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  validating: "Validating",
  preprocessing: "Preprocessing",
  chunking: "Chunking",
  embedding: "Embedding",
  completed: "Completed",
  failed: "Failed",
  validation_failed: "Validation Failed",
  duplicate_exact: "Duplicate (Exact)",
  duplicate_near: "Duplicate (Near)",
  access_denied: "Access Denied",
};

// ─── Types ───────────────────────────────────────────────────────────────────

interface TrackedJob {
  jobId: string;
  fileName: string;
  job: IngestionJob | null;
  error: string | null;
}

// ─── Helper Components ───────────────────────────────────────────────────────

const StatusBadge: FC<{ status: IngestionJobStatus }> = ({ status }) => {
  const variant = (() => {
    if (status === "completed") return "default";
    if (status === "failed" || status === "validation_failed" || status === "access_denied") return "destructive";
    if (status === "duplicate_exact" || status === "duplicate_near") return "outline";
    return "secondary";
  })();

  return <Badge variant={variant}>{STAGE_LABELS[status] || status}</Badge>;
};

const PipelineProgress: FC<{ status: IngestionJobStatus }> = ({ status }) => {
  const isTerminalError = ["failed", "validation_failed", "duplicate_exact", "duplicate_near", "access_denied"].includes(status);
  const currentIndex = PIPELINE_STAGES.indexOf(status);

  return (
    <div className="flex items-center gap-1">
      {PIPELINE_STAGES.map((stage, index) => {
        let stageClass = "bg-muted";
        if (isTerminalError) {
          stageClass = "bg-destructive/40";
        } else if (index < currentIndex) {
          stageClass = "bg-primary";
        } else if (index === currentIndex) {
          stageClass = status === "completed" ? "bg-primary" : "bg-primary/60 animate-pulse";
        }
        return (
          <div
            key={stage}
            className={`h-1.5 flex-1 rounded-full transition-colors ${stageClass}`}
            title={STAGE_LABELS[stage]}
          />
        );
      })}
    </div>
  );
};

// ─── Main Component ──────────────────────────────────────────────────────────

export const FileUpload: FC = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [department, setDepartment] = useState("");
  const [subfolder, setSubfolder] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [trackedJobs, setTrackedJobs] = useState<TrackedJob[]>([]);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ─── Drag and Drop Handlers ──────────────────────────────────────────────

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length > 0) {
      setFiles((prev) => [...prev, ...droppedFiles]);
    }
  }, []);

  // ─── File Picker Handler ─────────────────────────────────────────────────

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (selectedFiles.length > 0) {
      setFiles((prev) => [...prev, ...selectedFiles]);
    }
    // Reset input so the same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // ─── Upload Handler ──────────────────────────────────────────────────────

  const handleUpload = async () => {
    if (files.length === 0 || !department) return;

    setUploading(true);
    setUploadError(null);

    try {
      const response = await uploadBatch(files, department, subfolder || undefined);

      // Create tracked jobs from the response
      const newTrackedJobs: TrackedJob[] = response.jobs.map((job, index) => ({
        jobId: job.jobId,
        fileName: files[index]?.name || `File ${index + 1}`,
        job: null,
        error: null,
      }));

      setTrackedJobs((prev) => [...newTrackedJobs, ...prev]);
      setFiles([]);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  // ─── Job Status Polling ──────────────────────────────────────────────────

  useEffect(() => {
    const activeJobs = trackedJobs.filter(
      (tj) => tj.job === null || !isTerminalStatus(tj.job.status)
    );

    if (activeJobs.length === 0) {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      return;
    }

    const pollJobs = async () => {
      const updates = await Promise.allSettled(
        activeJobs.map((tj) => getJobDetail(tj.jobId))
      );

      setTrackedJobs((prev) =>
        prev.map((tj) => {
          const idx = activeJobs.findIndex((aj) => aj.jobId === tj.jobId);
          if (idx === -1) return tj;

          const result = updates[idx];
          if (result.status === "fulfilled") {
            return { ...tj, job: result.value, error: null };
          } else {
            return { ...tj, error: "Failed to fetch status" };
          }
        })
      );
    };

    // Poll immediately, then every 2 seconds
    pollJobs();
    pollingRef.current = setInterval(pollJobs, 2000);

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [trackedJobs.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Upload Form */}
      <div className="bg-card border border-border rounded-xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-foreground">Upload Files</h3>

        {/* Department Selection */}
        <div>
          <label className="block text-xs text-muted-foreground mb-1.5">
            Department <span className="text-destructive">*</span>
          </label>
          <select
            value={department}
            onChange={(e) => { setDepartment(e.target.value); setSubfolder(""); }}
            className="w-full bg-secondary border border-input rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:border-ring"
          >
            <option value="">Select department...</option>
            {Object.keys(DEPARTMENTS).map((d) => (
              <option key={d} value={d}>{DEPARTMENT_LABELS[d] || d}</option>
            ))}
          </select>
        </div>

        {/* Subfolder Selection */}
        <div>
          <label className="block text-xs text-muted-foreground mb-1.5">
            Subfolder <span className="text-muted-foreground/60">(optional)</span>
          </label>
          <select
            value={subfolder}
            onChange={(e) => setSubfolder(e.target.value)}
            disabled={!department}
            className="w-full bg-secondary border border-input rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:border-ring disabled:opacity-50"
          >
            <option value="">Select subfolder...</option>
            {department && DEPARTMENTS[department]?.map((s) => (
              <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
            ))}
          </select>
        </div>

        {/* Drag and Drop Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
          aria-label="Drop files here or click to browse"
          className={`
            relative flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 cursor-pointer transition-colors
            ${isDragOver
              ? "border-primary bg-primary/5 text-primary"
              : "border-input hover:border-primary/50 hover:bg-muted/50 text-muted-foreground"
            }
          `}
        >
          <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
          </svg>
          <div className="text-center">
            <p className="text-sm font-medium">
              {isDragOver ? "Drop files here" : "Drag & drop files here"}
            </p>
            <p className="text-xs mt-1">or click to browse</p>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            className="hidden"
            aria-hidden="true"
          />
        </div>

        {/* Selected Files List */}
        {files.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">{files.length} file{files.length > 1 ? "s" : ""} selected</p>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {files.map((file, index) => (
                <div key={`${file.name}-${index}`} className="flex items-center justify-between gap-2 px-3 py-1.5 bg-muted rounded-md">
                  <div className="flex items-center gap-2 min-w-0">
                    <svg className="w-4 h-4 text-muted-foreground shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                    </svg>
                    <span className="text-sm truncate">{file.name}</span>
                    <span className="text-xs text-muted-foreground shrink-0">
                      {formatFileSize(file.size)}
                    </span>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); removeFile(index); }}
                    className="text-muted-foreground hover:text-destructive transition-colors shrink-0"
                    aria-label={`Remove ${file.name}`}
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Upload Error */}
        {uploadError && (
          <div className="text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
            {uploadError}
          </div>
        )}

        {/* Upload Button */}
        <Button
          onClick={handleUpload}
          disabled={files.length === 0 || !department || uploading}
          className="w-full"
        >
          {uploading ? (
            <>
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Uploading...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
              </svg>
              Upload {files.length > 0 ? `${files.length} File${files.length > 1 ? "s" : ""}` : "Files"}
            </>
          )}
        </Button>
      </div>

      {/* Job Tracking */}
      {trackedJobs.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground">Upload Progress</h3>
            <Button
              variant="ghost"
              size="xs"
              onClick={() => setTrackedJobs([])}
            >
              Clear
            </Button>
          </div>

          <div className="space-y-3">
            {trackedJobs.map((tj) => (
              <div key={tj.jobId} className="border border-border rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium truncate">{tj.fileName}</span>
                  {tj.job && <StatusBadge status={tj.job.status} />}
                  {!tj.job && !tj.error && (
                    <Badge variant="secondary">Loading...</Badge>
                  )}
                </div>

                {tj.job && (
                  <PipelineProgress status={tj.job.status} />
                )}

                {/* Error details */}
                {tj.job && tj.job.status === "failed" && tj.job.errorMessage && (
                  <div className="text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded px-2 py-1.5 mt-1">
                    <span className="font-medium">Error:</span> {tj.job.errorMessage}
                    {tj.job.failureStage && (
                      <span className="text-muted-foreground ml-1">(at {tj.job.failureStage} stage)</span>
                    )}
                  </div>
                )}

                {/* Validation/access errors */}
                {tj.job && (tj.job.status === "validation_failed" || tj.job.status === "access_denied") && tj.job.errorMessage && (
                  <div className="text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded px-2 py-1.5 mt-1">
                    {tj.job.errorMessage}
                  </div>
                )}

                {/* Duplicate info */}
                {tj.job && (tj.job.status === "duplicate_exact" || tj.job.status === "duplicate_near") && (
                  <div className="text-xs text-muted-foreground bg-muted rounded px-2 py-1.5 mt-1">
                    This file was detected as a {tj.job.status === "duplicate_exact" ? "exact" : "near"} duplicate.
                  </div>
                )}

                {/* Polling error */}
                {tj.error && (
                  <p className="text-xs text-muted-foreground">{tj.error}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ─── Utilities ───────────────────────────────────────────────────────────────

function isTerminalStatus(status: IngestionJobStatus): boolean {
  return ["completed", "failed", "validation_failed", "duplicate_exact", "duplicate_near", "access_denied"].includes(status);
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const size = bytes / Math.pow(1024, i);
  return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
}

export default FileUpload;
