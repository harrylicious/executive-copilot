import { FileExplorer } from "./explorer/FileExplorer";

export function ExplorerPage() {
  return (
    <div className="flex flex-col h-full bg-background">
      <div className="px-6 py-4 border-b border-border shrink-0">
        <h2 className="text-sm font-medium text-foreground">Document Explorer</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Browse, preview, and manage your knowledge base documents
        </p>
      </div>
      <div className="flex-1 overflow-hidden">
        <FileExplorer />
      </div>
    </div>
  );
}

export default ExplorerPage;
