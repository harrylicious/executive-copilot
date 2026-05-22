import { useState, useEffect, useCallback, type FC } from "react";
import { getBatchConfigs, createBatchConfig } from "../../api/ingestion";
import type {
  BatchLoaderConfig as BatchLoaderConfigType,
  BatchLoaderConfigCreate,
  BatchSourceType,
} from "../../types/ingestion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// ─── Constants ───────────────────────────────────────────────────────────────

const DEPARTMENTS = [
  "demand_supply",
  "accounting_tax",
  "logistic",
  "finance",
];

const DEPARTMENT_LABELS: Record<string, string> = {
  demand_supply: "Demand-Supply Planning",
  accounting_tax: "Controller Accounting Tax",
  logistic: "Logistic",
  finance: "Finance",
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function getStatusVariant(
  status: string | null
): "default" | "secondary" | "destructive" {
  if (!status) return "secondary";
  if (status === "completed") return "default";
  if (status === "failed") return "destructive";
  return "secondary";
}

// ─── Form State ──────────────────────────────────────────────────────────────

interface ConfigFormData {
  name: string;
  sourcePath: string;
  sourceType: BatchSourceType;
  cronExpression: string;
  department: string;
  subfolder: string;
}

const EMPTY_FORM: ConfigFormData = {
  name: "",
  sourcePath: "",
  sourceType: "local",
  cronExpression: "",
  department: "",
  subfolder: "",
};

// ─── Component ───────────────────────────────────────────────────────────────

export const BatchLoaderConfig: FC = () => {
  const [configs, setConfigs] = useState<BatchLoaderConfigType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingConfig, setEditingConfig] =
    useState<BatchLoaderConfigType | null>(null);
  const [formData, setFormData] = useState<ConfigFormData>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // ─── Data Fetching ───────────────────────────────────────────────────────

  const fetchConfigs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getBatchConfigs();
      setConfigs(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load configs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfigs();
  }, [fetchConfigs]);

  // ─── Form Handlers ─────────────────────────────────────────────────────

  const openCreateDialog = () => {
    setEditingConfig(null);
    setFormData(EMPTY_FORM);
    setSubmitError(null);
    setDialogOpen(true);
  };

  const openEditDialog = (config: BatchLoaderConfigType) => {
    setEditingConfig(config);
    setFormData({
      name: config.name,
      sourcePath: config.sourcePath,
      sourceType: config.sourceType,
      cronExpression: config.cronExpression,
      department: config.department,
      subfolder: config.subfolder ?? "",
    });
    setSubmitError(null);
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.sourcePath || !formData.cronExpression || !formData.department) {
      setSubmitError("Please fill in all required fields.");
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      const payload: BatchLoaderConfigCreate = {
        name: formData.name,
        sourcePath: formData.sourcePath,
        sourceType: formData.sourceType,
        cronExpression: formData.cronExpression,
        department: formData.department,
        subfolder: formData.subfolder || null,
      };

      // For edit mode, we'd call an update endpoint. For now, create only.
      if (!editingConfig) {
        await createBatchConfig(payload);
      }
      // TODO: Add updateBatchConfig API call for edit mode

      setDialogOpen(false);
      fetchConfigs();
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "Failed to save configuration"
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (config: BatchLoaderConfigType) => {
    // Toggle active state - would call an update endpoint
    // For now, optimistically update the UI
    setConfigs((prev) =>
      prev.map((c) =>
        c.id === config.id ? { ...c, isActive: !c.isActive } : c
      )
    );
    // TODO: Call updateBatchConfig API to persist the toggle
  };

  // ─── Render ────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
        <svg
          className="animate-spin w-4 h-4 mr-2 text-primary"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        Loading batch configurations...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-sm">
        <p className="text-destructive mb-2">Failed to load batch configurations</p>
        <p className="text-muted-foreground text-xs mb-3">{error}</p>
        <Button variant="secondary" size="sm" onClick={fetchConfigs}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">
          Batch Loader Configurations
        </h2>
        <Button onClick={openCreateDialog} size="sm">
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 4v16m8-8H4"
            />
          </svg>
          Create New
        </Button>
      </div>

      {/* Config List */}
      {configs.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground text-sm">
          No batch loader configurations found. Create one to get started.
        </div>
      ) : (
        <div className="border border-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">
                  Name
                </th>
                <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">
                  Source
                </th>
                <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">
                  Schedule
                </th>
                <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">
                  Department
                </th>
                <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">
                  Last Execution
                </th>
                <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">
                  Next Execution
                </th>
                <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">
                  Status
                </th>
                <th className="text-right px-4 py-2.5 font-medium text-muted-foreground">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {configs.map((config) => (
                <tr
                  key={config.id}
                  className="border-b border-border last:border-b-0 hover:bg-muted/30 transition-colors"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-foreground">
                        {config.name}
                      </span>
                      {!config.isActive && (
                        <Badge variant="secondary" className="text-[10px]">
                          Inactive
                        </Badge>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col">
                      <span className="text-foreground truncate max-w-[200px]">
                        {config.sourcePath}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {config.sourceType === "s3" ? "S3" : "Local"}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground font-mono text-xs">
                    {config.cronExpression}
                  </td>
                  <td className="px-4 py-3 text-foreground">
                    {DEPARTMENT_LABELS[config.department] ?? config.department}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">
                    {formatDateTime(config.lastExecutionAt)}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">
                    {formatDateTime(config.nextExecutionAt)}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={getStatusVariant(config.lastExecutionStatus)}>
                      {config.lastExecutionStatus ?? "Never run"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="xs"
                        onClick={() => openEditDialog(config)}
                        title="Edit configuration"
                      >
                        <svg
                          className="w-3.5 h-3.5"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth={2}
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z"
                          />
                        </svg>
                      </Button>
                      <Button
                        variant={config.isActive ? "ghost" : "ghost"}
                        size="xs"
                        onClick={() => handleToggleActive(config)}
                        title={
                          config.isActive
                            ? "Deactivate configuration"
                            : "Activate configuration"
                        }
                      >
                        {config.isActive ? (
                          <svg
                            className="w-3.5 h-3.5 text-green-500"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={2}
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M5.636 5.636a9 9 0 1012.728 0M12 3v9"
                            />
                          </svg>
                        ) : (
                          <svg
                            className="w-3.5 h-3.5 text-muted-foreground"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={2}
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M5.636 5.636a9 9 0 1012.728 0M12 3v9"
                            />
                          </svg>
                        )}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>
              {editingConfig
                ? "Edit Batch Loader Configuration"
                : "Create Batch Loader Configuration"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Name */}
            <div>
              <label className="block text-xs text-muted-foreground mb-1.5">
                Name <span className="text-destructive">*</span>
              </label>
              <Input
                value={formData.name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, name: e.target.value }))
                }
                placeholder="e.g., Daily Finance Reports"
              />
            </div>

            {/* Source Path */}
            <div>
              <label className="block text-xs text-muted-foreground mb-1.5">
                Source Path <span className="text-destructive">*</span>
              </label>
              <Input
                value={formData.sourcePath}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    sourcePath: e.target.value,
                  }))
                }
                placeholder={
                  formData.sourceType === "s3"
                    ? "s3://bucket-name/prefix"
                    : "/path/to/documents"
                }
              />
            </div>

            {/* Source Type */}
            <div>
              <label className="block text-xs text-muted-foreground mb-1.5">
                Source Type <span className="text-destructive">*</span>
              </label>
              <Select
                value={formData.sourceType}
                onValueChange={(value) =>
                  setFormData((prev) => ({
                    ...prev,
                    sourceType: value as BatchSourceType,
                  }))
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select source type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="local">Local Filesystem</SelectItem>
                  <SelectItem value="s3">Amazon S3</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Cron Expression */}
            <div>
              <label className="block text-xs text-muted-foreground mb-1.5">
                Cron Expression <span className="text-destructive">*</span>
              </label>
              <Input
                value={formData.cronExpression}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    cronExpression: e.target.value,
                  }))
                }
                placeholder="0 */6 * * * (every 6 hours)"
                className="font-mono"
              />
              <p className="text-[11px] text-muted-foreground mt-1">
                Standard cron format: minute hour day month weekday
              </p>
            </div>

            {/* Department */}
            <div>
              <label className="block text-xs text-muted-foreground mb-1.5">
                Department <span className="text-destructive">*</span>
              </label>
              <Select
                value={formData.department}
                onValueChange={(value) =>
                  setFormData((prev) => ({ ...prev, department: value }))
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select department" />
                </SelectTrigger>
                <SelectContent>
                  {DEPARTMENTS.map((dept) => (
                    <SelectItem key={dept} value={dept}>
                      {DEPARTMENT_LABELS[dept] ?? dept}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Subfolder */}
            <div>
              <label className="block text-xs text-muted-foreground mb-1.5">
                Subfolder
              </label>
              <Input
                value={formData.subfolder}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    subfolder: e.target.value,
                  }))
                }
                placeholder="Optional subfolder path"
              />
            </div>

            {/* Error */}
            {submitError && (
              <div className="text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
                {submitError}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="secondary"
              onClick={() => setDialogOpen(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting ? (
                <>
                  <svg
                    className="w-4 h-4 animate-spin"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  Saving...
                </>
              ) : editingConfig ? (
                "Save Changes"
              ) : (
                "Create Configuration"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default BatchLoaderConfig;
