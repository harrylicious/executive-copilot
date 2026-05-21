import { useState, useCallback, useEffect } from "react";
import type { FileNode } from "../types";
import { FileViewer } from "../components/FileViewer/FileViewer";
import { FileExplorer } from "../components/FileExplorer/FileExplorer";
import { MetadataSidebar } from "../components/MetadataSidebar/MetadataSidebar";
import useGraph from "../hooks/useGraph";
import { getFile } from "../api/client";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useSidebarContent } from "../components/Layout/SidebarContentContext";

export function ExplorerPage() {
  const [selectedFile, setSelectedFile] = useState<FileNode | null>(null);
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const setSidebarContent = useSidebarContent();

  const { fetchGraph } = useGraph();

  const handleFileSelect = useCallback(async (fileId: number) => {
    try {
      const file = await getFile(fileId);
      setSelectedFile(file);
    } catch {
      setSelectedFile(null);
    }
  }, []);

  const handleTagsUpdated = useCallback(
    (updatedFile: FileNode) => {
      setSelectedFile(updatedFile);
      fetchGraph();
    },
    [fetchGraph]
  );

  // Inject file explorer into the sidebar
  useEffect(() => {
    setSidebarContent(
      <ScrollArea className="h-full">
        <FileExplorer onFileSelect={handleFileSelect} />
      </ScrollArea>
    );
    return () => setSidebarContent(null);
  }, [setSidebarContent, handleFileSelect]);

  // Check for fileId query parameter (used by source attribution navigation)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const fileId = params.get("fileId");
    if (fileId) {
      handleFileSelect(Number(fileId));
    }
  }, [handleFileSelect]);

  return (
    <div className="flex h-full overflow-hidden">
      {/* Center: File Viewer */}
      <div className="flex-1 overflow-hidden relative">
        <Button
          variant="ghost"
          size="icon-sm"
          className="absolute top-2 right-2 z-10"
          onClick={() => setRightPanelOpen((p) => !p)}
          aria-label={rightPanelOpen ? "Hide details" : "Show details"}
        >
          {rightPanelOpen ? (
            <PanelRightClose className="size-4" />
          ) : (
            <PanelRightOpen className="size-4" />
          )}
        </Button>
        <FileViewer file={selectedFile} />
      </div>

      {/* Right: Metadata Sidebar */}
      {rightPanelOpen && (
        <div className="w-64 min-w-[16rem] border-l border-border bg-card shrink-0">
          <ScrollArea className="h-full">
            <MetadataSidebar
              file={selectedFile}
              onTagsUpdated={handleTagsUpdated}
            />
          </ScrollArea>
        </div>
      )}
    </div>
  );
}

export default ExplorerPage;
