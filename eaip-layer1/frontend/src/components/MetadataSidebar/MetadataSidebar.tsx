import type { FC } from "react";
import type { FileNode } from "../../types";
import { TagEditor } from "./TagEditor";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

interface MetadataSidebarProps {
  file: FileNode | null;
  onTagsUpdated?: (file: FileNode) => void;
}

const DEPARTMENT_COLORS: Record<string, string> = {
  demand_supply: "bg-purple-600/20 text-purple-400 border-purple-600/40",
  accounting_tax: "bg-teal-600/20 text-teal-400 border-teal-600/40",
  logistic: "bg-amber-600/20 text-amber-400 border-amber-600/40",
  finance: "bg-orange-600/20 text-orange-400 border-orange-600/40",
};

const SYNC_STATUS_COLORS: Record<string, string> = {
  synced: "bg-green-600/20 text-green-400",
  modified: "bg-yellow-600/20 text-yellow-400",
  pending: "bg-orange-600/20 text-orange-400",
  syncing: "bg-blue-600/20 text-blue-400",
  error: "bg-red-600/20 text-red-400",
  deleted: "bg-gray-600/20 text-gray-400",
};

function getDepartmentBadgeClass(department: string): string {
  return (
    DEPARTMENT_COLORS[department] ??
    "bg-gray-600/20 text-gray-400 border-gray-600/40"
  );
}

function getSyncStatusClass(status: string | undefined): string {
  return SYNC_STATUS_COLORS[status ?? ""] ?? "bg-gray-600/20 text-gray-400";
}

function getSensitivityBadgeClass(level: string | undefined): string {
  const colors: Record<string, string> = {
    Confidential: "bg-red-600/20 text-red-400 border-red-600/40",
    Internal: "bg-blue-600/20 text-blue-400 border-blue-600/40",
    Public_Internal: "bg-green-600/20 text-green-400 border-green-600/40",
  };
  return colors[level ?? ""] ?? "bg-gray-600/20 text-gray-400 border-gray-600/40";
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export const MetadataSidebar: FC<MetadataSidebarProps> = ({
  file,
  onTagsUpdated,
}) => {
  if (!file) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        Select a file to view metadata
      </div>
    );
  }

  return (
    <Card className="h-full rounded-none border-0 shadow-none">
      <CardHeader className="pb-0">
        <CardTitle className="text-sm break-all">{file.name}</CardTitle>
      </CardHeader>

      <CardContent className="space-y-3 text-sm">
        <div>
          <span className="text-muted-foreground block text-xs uppercase tracking-wide">
            Path
          </span>
          <span className="text-card-foreground break-all">{file.path}</span>
        </div>

        <div>
          <span className="text-muted-foreground block text-xs uppercase tracking-wide">
            Department
          </span>
          <Badge
            variant="outline"
            className={`mt-1 rounded ${getDepartmentBadgeClass(file.department)}`}
          >
            {file.department.replace(/_/g, " ")}
          </Badge>
        </div>

        {file.syncStatus && (
          <div>
            <span className="text-muted-foreground block text-xs uppercase tracking-wide">
              Sync Status
            </span>
            <Badge
              variant="outline"
              className={`mt-1 rounded border-transparent ${getSyncStatusClass(file.syncStatus)}`}
            >
              {file.syncStatus}
            </Badge>
          </div>
        )}

        {file.sensitivityLevel && (
          <div>
            <span className="text-muted-foreground block text-xs uppercase tracking-wide">
              Sensitivity
            </span>
            <Badge
              variant="outline"
              className={`mt-1 rounded ${getSensitivityBadgeClass(file.sensitivityLevel)}`}
            >
              {file.sensitivityLevel.replace(/_/g, " ")}
            </Badge>
          </div>
        )}

        <div>
          <span className="text-muted-foreground block text-xs uppercase tracking-wide">
            Size
          </span>
          <span className="text-card-foreground">{formatFileSize(file.size)}</span>
        </div>

        <div>
          <span className="text-muted-foreground block text-xs uppercase tracking-wide">
            Created
          </span>
          <span className="text-card-foreground">{formatDate(file.createdAt)}</span>
        </div>

        <div>
          <span className="text-muted-foreground block text-xs uppercase tracking-wide">
            Modified
          </span>
          <span className="text-card-foreground">{formatDate(file.modifiedAt)}</span>
        </div>

        {file.indexedAt && (
          <div>
            <span className="text-muted-foreground block text-xs uppercase tracking-wide">
              Indexed
            </span>
            <span className="text-card-foreground">{formatDate(file.indexedAt)}</span>
          </div>
        )}

        <Separator />

        <TagEditor
          fileId={file.id}
          tags={file.tags}
          onTagsUpdated={onTagsUpdated}
        />
      </CardContent>
    </Card>
  );
};

export default MetadataSidebar;
