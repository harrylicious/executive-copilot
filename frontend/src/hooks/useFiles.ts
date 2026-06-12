import { useState, useEffect, useCallback } from "react";
import type { FileNode, TreeNode } from "../types";
import { getDepartments, getFiles } from "../api/kb";

interface UseFilesReturn {
  tree: TreeNode[];
  treeLoading: boolean;
  treeError: string | null;
  files: FileNode[];
  filesLoading: boolean;
  filesError: string | null;
  refresh: () => void;
  removeNode: (nodeId: string) => void;
}

export function useFiles(): UseFilesReturn {
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [treeLoading, setTreeLoading] = useState(true);
  const [treeError, setTreeError] = useState<string | null>(null);
  const [files, setFiles] = useState<FileNode[]>([]);
  const [filesLoading, setFilesLoading] = useState(true);
  const [filesError, setFilesError] = useState<string | null>(null);

  const fetchTree = useCallback(async () => {
    setTreeLoading(true);
    setTreeError(null);
    try {
      const data = await getDepartments();
      setTree(data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load file tree";
      setTreeError(message);
    } finally {
      setTreeLoading(false);
    }
  }, []);

  const fetchFiles = useCallback(async () => {
    setFilesLoading(true);
    setFilesError(null);
    try {
      const data = await getFiles();
      setFiles(data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load files";
      setFilesError(message);
    } finally {
      setFilesLoading(false);
    }
  }, []);

  const refresh = useCallback(() => {
    fetchTree();
    fetchFiles();
  }, [fetchTree, fetchFiles]);

  const removeNode = useCallback((nodeId: string) => {
    function prune(nodes: TreeNode[]): TreeNode[] {
      return nodes
        .filter((n) => n.id !== nodeId)
        .map((n) => ({
          ...n,
          children: n.children ? prune(n.children) : undefined,
        }));
    }
    setTree((prev) => prune(prev));
  }, []);

  useEffect(() => {
    fetchTree();
    fetchFiles();
  }, [fetchTree, fetchFiles]);

  return {
    tree,
    treeLoading,
    treeError,
    files,
    filesLoading,
    filesError,
    refresh,
    removeNode,
  };
}

export default useFiles;
