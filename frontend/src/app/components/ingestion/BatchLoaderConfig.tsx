import { useState, useEffect } from "react";
import { Plus, Loader2, RefreshCw, CheckCircle2, XCircle, Play, StopCircle } from "lucide-react";
import { getBatchConfigs, createBatchConfig } from "../../../api/ingestion";
import type { BatchLoaderConfig as BatchConfig, BatchLoaderConfigCreate } from "../../../types/ingestion";

export function BatchLoaderConfig() {
  const [configs, setConfigs] = useState<BatchConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  // Form state
  const [form, setForm] = useState<BatchLoaderConfigCreate>({
    name: "",
    sourcePath: "",
    sourceType: "local",
    cronExpression: "0 0 * * *",
    department: "",
    subfolder: "",
  });

  const fetchConfigs = async () => {
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
  };

  useEffect(() => {
    fetchConfigs();
  }, []);

  const handleCreate = async () => {
    if (!form.name || !form.sourcePath || !form.department) return;
    setSaving(true);
    try {
      await createBatchConfig({
        ...form,
        subfolder: form.subfolder || null,
      });
      setFormOpen(false);
      setForm({
        name: "", sourcePath: "", sourceType: "local",
        cronExpression: "0 0 * * *", department: "", subfolder: "",
      });
      await fetchConfigs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create config");
    } finally {
      setSaving(false);
    }
  };

  const statusBadge = (status: string | null) => {
    if (!status) return null;
    const colors: Record<string, string> = {
      completed: "bg-emerald-500/10 text-emerald-500",
      running: "bg-amber-500/10 text-amber-500",
      failed: "bg-red-500/10 text-red-500",
    };
    return (
      <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${colors[status] || "bg-muted text-muted-foreground"}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="space-y-4">
      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-500">
          <XCircle size={12} />
          {error}
          <button onClick={fetchConfigs} className="ml-auto hover:underline">Retry</button>
        </div>
      )}

      {/* Header + Create button */}
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-medium text-foreground">Batch Loader Configurations</h4>
        <div className="flex gap-2">
          <button
            onClick={fetchConfigs}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-secondary-foreground hover:bg-card transition-colors"
          >
            <RefreshCw size={13} />
          </button>
          <button
            onClick={() => setFormOpen(!formOpen)}
            className="flex items-center gap-1 bg-primary hover:bg-primary/90 text-primary-foreground text-xs rounded-lg px-3 py-1.5 transition-colors"
          >
            <Plus size={12} />
            New Config
          </button>
        </div>
      </div>

      {/* Create form */}
      {formOpen && (
        <div className="bg-card border border-border rounded-xl p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">Name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full bg-input border border-border rounded-lg px-3 py-1.5 text-xs text-foreground focus:outline-none focus:border-primary/40" />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">Source Type</label>
              <select value={form.sourceType} onChange={(e) => setForm({ ...form, sourceType: e.target.value as "local" | "s3" })}
                className="w-full bg-input border border-border rounded-lg px-3 py-1.5 text-xs text-foreground focus:outline-none focus:border-primary/40">
                <option value="local">Local</option>
                <option value="s3">S3</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">Source Path</label>
              <input value={form.sourcePath} onChange={(e) => setForm({ ...form, sourcePath: e.target.value })}
                className="w-full bg-input border border-border rounded-lg px-3 py-1.5 text-xs text-foreground focus:outline-none focus:border-primary/40" />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">Cron Expression</label>
              <input value={form.cronExpression} onChange={(e) => setForm({ ...form, cronExpression: e.target.value })}
                className="w-full bg-input border border-border rounded-lg px-3 py-1.5 text-xs text-foreground focus:outline-none focus:border-primary/40" />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">Department</label>
              <input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}
                className="w-full bg-input border border-border rounded-lg px-3 py-1.5 text-xs text-foreground focus:outline-none focus:border-primary/40" />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground">Subfolder (optional)</label>
              <input value={form.subfolder || ""} onChange={(e) => setForm({ ...form, subfolder: e.target.value })}
                className="w-full bg-input border border-border rounded-lg px-3 py-1.5 text-xs text-foreground focus:outline-none focus:border-primary/40" />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button onClick={() => setFormOpen(false)}
              className="px-3 py-1.5 text-xs text-muted-foreground hover:text-secondary-foreground rounded-lg transition-colors">
              Cancel
            </button>
            <button onClick={handleCreate} disabled={saving || !form.name || !form.sourcePath || !form.department}
              className="flex items-center gap-1 bg-primary hover:bg-primary/90 disabled:opacity-40 text-primary-foreground text-xs rounded-lg px-4 py-1.5 transition-colors">
              {saving ? <Loader2 size={12} className="animate-spin" /> : null}
              Save
            </button>
          </div>
        </div>
      )}

      {/* Config list */}
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 size={16} className="animate-spin text-muted-foreground" />
        </div>
      ) : configs.length === 0 ? (
        <p className="text-xs text-muted-foreground text-center py-8">No batch configurations yet</p>
      ) : (
        <div className="space-y-2">
          {configs.map((config) => (
            <div
              key={config.id}
              className="bg-card border border-border rounded-xl p-4 flex items-center justify-between"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground truncate">{config.name}</span>
                  {config.isActive && (
                    <span className="bg-emerald-500/10 text-emerald-500 text-[10px] px-1.5 py-0.5 rounded-full">Active</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1 text-[10px] text-muted-foreground">
                  <span>{config.sourcePath}</span>
                  <span className="uppercase">({config.sourceType})</span>
                  <span>· {config.department}</span>
                  {config.cronExpression && <span>· cron: {config.cronExpression}</span>}
                </div>
                {(config.lastExecutionAt || config.lastExecutionStatus) && (
                  <div className="flex items-center gap-2 mt-1.5">
                    {config.lastExecutionAt && (
                      <span className="text-[10px] text-muted-foreground">
                        Last: {new Date(config.lastExecutionAt).toLocaleDateString("id-ID", {
                          day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"
                        })}
                      </span>
                    )}
                    {statusBadge(config.lastExecutionStatus)}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default BatchLoaderConfig;
