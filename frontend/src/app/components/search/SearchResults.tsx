import { useState, useRef, useMemo } from "react";
import { Search, SlidersHorizontal, FileText, Loader2, AlertCircle, Sparkles, ChevronDown, List, Layers } from "lucide-react";
import { cn } from "../../../utils/cn";
import { localSearch, globalSearch, combinedSearch } from "../../../api/kb";
import { FileViewer } from "../FileViewer";
import type {
  SearchResponse,
  ChunkResult,
  CommunityResult,
  SourceAttribution,
  SearchMode,
} from "../../../types";

type ResultTab = "chunks" | "communities" | "attributions";
type ChunksViewMode = "flat" | "grouped";

interface FileViewerDoc {
  id: string; name: string; type: string; size: string; dept: string;
  uploadedBy: string; uploadedAt: string; pages?: number; chunks?: number; status?: string;
}

const DEPARTMENTS = ["accounting_tax", "demand_supply", "finance", "logistic", "master"] as const;

/** Highlight matching words from the search query within a text snippet */
function highlightText(text: string, searchQuery: string): React.ReactNode {
  if (!searchQuery.trim()) return text;
  const words = searchQuery
    .trim()
    .split(/\s+/)
    .filter((w) => w.length > 0)
    .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (words.length === 0) return text;
  const pattern = new RegExp(`(${words.join("|")})`, "gi");
  const parts = text.split(pattern);
  return parts.map((part, i) =>
    pattern.test(part) ? (
      <mark key={i} className="bg-yellow-500/20 text-inherit rounded-sm px-0.5">
        {part}
      </mark>
    ) : (
      part
    )
  );
}

/** Group chunks by file name */
function groupChunksByFile(chunks: ChunkResult[]): Map<string, ChunkResult[]> {
  const groups = new Map<string, ChunkResult[]>();
  for (const chunk of chunks) {
    const key = chunk.fileName;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(chunk);
  }
  return groups;
}

export function SearchResults() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("combined");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ResultTab>("chunks");
  const [viewerDoc, setViewerDoc] = useState<FileViewerDoc | null>(null);
  const [expandedCommunities, setExpandedCommunities] = useState<Set<number>>(new Set());
  const [departmentFilter, setDepartmentFilter] = useState<string>("all");
  const [minScore, setMinScore] = useState<number>(0);
  const [chunksViewMode, setChunksViewMode] = useState<ChunksViewMode>("flat");
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSearch = async () => {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      let res: SearchResponse;
      switch (mode) {
        case "local":
          res = await localSearch({ query: q, topK: 10 });
          break;
        case "global":
          res = await globalSearch({ query: q, numCommunities: 5 });
          break;
        case "combined":
        default:
          res = await combinedSearch({ query: q, topK: 10, numCommunities: 5 });
          break;
      }
      setResults(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  const openFileViewer = (chunk: ChunkResult) => {
    setViewerDoc({
      id: chunk.fileId.toString(),
      name: chunk.fileName,
      type: chunk.fileName.split(".").pop()?.toLowerCase() || "txt",
      size: "—",
      dept: chunk.department,
      uploadedBy: "—",
      uploadedAt: "—",
      pages: undefined,
      chunks: undefined,
      status: undefined,
    });
  };

  const toggleCommunity = (id: number) => {
    setExpandedCommunities((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const uniqueAttributions = results?.sourceAttributions?.filter(
    (a, i, arr) => arr.findIndex((x) => x.fileId === a.fileId) === i
  ) || [];

  const filteredChunks = results?.chunks.filter((chunk) => {
    if (departmentFilter !== "all" && chunk.department !== departmentFilter) return false;
    if (minScore > 0 && chunk.score < minScore) return false;
    return true;
  }) || [];

  const groupedChunks = useMemo(() => groupChunksByFile(filteredChunks), [filteredChunks]);

  const toggleGroup = (fileName: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(fileName)) next.delete(fileName);
      else next.add(fileName);
      return next;
    });
  };

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Search bar */}
      <div className="px-6 py-4 border-b border-border shrink-0">
        <div className="flex items-center gap-2 max-w-2xl mx-auto">
          <div className="flex-1 relative">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search documents..."
              className="w-full bg-card border border-border rounded-xl pl-10 pr-4 py-2.5 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-primary/40"
            />
          </div>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as SearchMode)}
            className="bg-card border border-border rounded-xl px-3 py-2.5 text-xs text-secondary-foreground focus:outline-none focus:border-primary/40"
          >
            <option value="local">Local</option>
            <option value="global">Global</option>
            <option value="combined">Combined</option>
          </select>
          <button
            onClick={handleSearch}
            disabled={!query.trim() || loading}
            className="bg-primary hover:bg-primary/90 disabled:opacity-40 text-primary-foreground rounded-xl px-4 py-2.5 text-sm font-medium transition-colors"
          >
            {loading ? <Loader2 size={15} className="animate-spin" /> : "Search"}
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-4 max-w-2xl mx-auto mt-3">
          <div className="flex items-center gap-2">
            <label htmlFor="dept-filter" className="text-xs text-muted-foreground">Department:</label>
            <select
              id="dept-filter"
              value={departmentFilter}
              onChange={(e) => setDepartmentFilter(e.target.value)}
              className="bg-card border border-border rounded-lg px-2.5 py-1.5 text-xs text-secondary-foreground focus:outline-none focus:border-primary/40"
            >
              <option value="all">All Departments</option>
              {DEPARTMENTS.map((dept) => (
                <option key={dept} value={dept}>{dept}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="min-score" className="text-xs text-muted-foreground">Min Score:</label>
            <input
              id="min-score"
              type="range"
              min={0}
              max={1}
              step={0.1}
              value={minScore}
              onChange={(e) => setMinScore(parseFloat(e.target.value))}
              className="w-24 h-1.5 accent-primary"
            />
            <span className="text-xs text-secondary-foreground tabular-nums w-8">{minScore.toFixed(1)}</span>
          </div>
        </div>
      </div>

      {/* Results area */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center py-16">
            <div className="flex flex-col items-center gap-2">
              <Loader2 size={22} className="animate-spin text-primary" />
              <span className="text-xs text-muted-foreground">Searching...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center py-16 px-4">
            <div className="w-12 h-12 rounded-2xl bg-destructive/10 flex items-center justify-center mb-3">
              <AlertCircle size={22} className="text-destructive" />
            </div>
            <p className="text-sm font-medium text-destructive mb-1">Pencarian gagal</p>
            <p className="text-xs text-muted-foreground mb-3 max-w-xs text-center">{error}</p>
            <button
              onClick={handleSearch}
              className="bg-primary hover:bg-primary/90 text-primary-foreground rounded-lg px-4 py-2 text-xs font-medium transition-colors"
            >
              Coba lagi
            </button>
          </div>
        )}

        {!loading && !error && !results && (
          <div className="flex flex-col items-center justify-center py-24 px-4 text-center">
            <div className="w-12 h-12 rounded-2xl bg-primary/5 flex items-center justify-center mb-3">
              <Search size={22} className="text-muted-foreground/40" />
            </div>
            <p className="text-sm text-muted-foreground mb-1">Try searching for documents</p>
            <p className="text-xs text-muted-foreground/60">
              Enter a query and press Enter or click Search
            </p>
          </div>
        )}

        {results && !loading && (
          <div className="max-w-4xl mx-auto px-6 py-6 space-y-4">
            {/* Metadata summary bar */}
            <div className="flex items-center gap-4 bg-card border border-border rounded-xl px-4 py-2.5">
              <div className="flex items-center gap-1.5">
                <SlidersHorizontal size={12} className="text-primary" />
                <span className="text-xs font-medium text-secondary-foreground">Search Summary</span>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-muted-foreground ml-auto">
                <span className="flex items-center gap-1">
                  <span className="font-medium text-secondary-foreground">{results.metadata.queryTimeMs}</span>ms
                </span>
                <span className="text-border">|</span>
                <span className="flex items-center gap-1">
                  <span className="font-medium text-secondary-foreground">{results.metadata.totalChunksSearched}</span> chunks searched
                </span>
                <span className="text-border">|</span>
                <span className="capitalize flex items-center gap-1">
                  Mode: <span className="font-medium text-secondary-foreground">{results.metadata.retrievalMode}</span>
                </span>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-border pb-2">
              {(["chunks", "communities", "attributions"] as ResultTab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    "px-3 py-1.5 text-xs rounded-lg transition-all capitalize",
                    activeTab === tab
                      ? "bg-secondary text-foreground border border-border"
                      : "text-muted-foreground hover:text-secondary-foreground"
                  )}
                >
                  {tab === "chunks" ? `Chunks (${filteredChunks.length})` :
                   tab === "communities" ? `Communities (${results.communitySummaries.length})` :
                   `Sources (${uniqueAttributions.length})`}
                </button>
              ))}
            </div>

            {/* Chunks tab */}
            {activeTab === "chunks" && (
              <div className="space-y-3">
                {/* View mode toggle */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">View:</span>
                  <div className="flex bg-muted rounded-lg p-0.5">
                    <button
                      onClick={() => setChunksViewMode("flat")}
                      className={cn(
                        "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition-colors",
                        chunksViewMode === "flat"
                          ? "bg-card text-foreground shadow-sm border border-border"
                          : "text-muted-foreground hover:text-secondary-foreground"
                      )}
                    >
                      <List size={12} />
                      Flat
                    </button>
                    <button
                      onClick={() => setChunksViewMode("grouped")}
                      className={cn(
                        "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition-colors",
                        chunksViewMode === "grouped"
                          ? "bg-card text-foreground shadow-sm border border-border"
                          : "text-muted-foreground hover:text-secondary-foreground"
                      )}
                    >
                      <Layers size={12} />
                      Grouped
                    </button>
                  </div>
                </div>

                {filteredChunks.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
                    <div className="w-12 h-12 rounded-2xl bg-muted/50 flex items-center justify-center mb-3">
                      <Search size={22} className="text-muted-foreground/40" />
                    </div>
                    <p className="text-sm font-medium text-secondary-foreground mb-1">
                      Tidak ditemukan hasil untuk pencarian ini
                    </p>
                    <p className="text-xs text-muted-foreground mb-4">Coba salah satu saran berikut:</p>
                    <ul className="space-y-1.5 text-xs text-muted-foreground">
                      <li className="flex items-center gap-2">
                        <span className="w-1 h-1 rounded-full bg-primary/60 shrink-0" />
                        Gunakan kata kunci yang lebih umum
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1 h-1 rounded-full bg-primary/60 shrink-0" />
                        Periksa ejaan kata kunci Anda
                      </li>
                      <li className="flex items-center gap-2">
                        <span className="w-1 h-1 rounded-full bg-primary/60 shrink-0" />
                        Coba filter departemen yang berbeda
                      </li>
                    </ul>
                  </div>
                )}

                {/* Flat view */}
                {chunksViewMode === "flat" && filteredChunks.length > 0 && (
                  <div className="space-y-3">
                    {filteredChunks.map((chunk, i) => (
                      <ChunkCard
                        key={`${chunk.fileId}-${chunk.chunkIndex}-${i}`}
                        chunk={chunk}
                        searchQuery={query}
                        onOpenFile={openFileViewer}
                      />
                    ))}
                  </div>
                )}

                {/* Grouped view */}
                {chunksViewMode === "grouped" && filteredChunks.length > 0 && (
                  <div className="space-y-2">
                    {Array.from(groupedChunks.entries()).map(([fileName, chunks]) => {
                      const isCollapsed = collapsedGroups.has(fileName);
                      const dept = chunks[0]?.department || "";
                      return (
                        <div key={fileName} className="border border-border rounded-xl overflow-hidden">
                          {/* Group header */}
                          <button
                            onClick={() => toggleGroup(fileName)}
                            className="w-full flex items-center justify-between p-3 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <FileText size={14} className="text-primary shrink-0" />
                              <span className="text-xs font-medium text-secondary-foreground truncate">
                                {fileName}
                              </span>
                              <span className="text-[10px] bg-secondary text-secondary-foreground px-2 py-0.5 rounded-md shrink-0">
                                {dept}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <span className="text-[10px] text-muted-foreground bg-muted px-2 py-0.5 rounded-md">
                                {chunks.length} {chunks.length === 1 ? "chunk" : "chunks"}
                              </span>
                              <ChevronDown
                                size={14}
                                className={cn(
                                  "text-muted-foreground transition-transform",
                                  isCollapsed && "-rotate-90"
                                )}
                              />
                            </div>
                          </button>
                          {/* Group content */}
                          {!isCollapsed && (
                            <div className="p-3 space-y-3 border-t border-border">
                              {chunks.map((chunk, i) => (
                                <ChunkCard
                                  key={`${chunk.fileId}-${chunk.chunkIndex}-${i}`}
                                  chunk={chunk}
                                  searchQuery={query}
                                  onOpenFile={openFileViewer}
                                />
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Communities tab */}
            {activeTab === "communities" && (
              <div className="space-y-3">
                {results.communitySummaries.length === 0 && (
                  <p className="text-xs text-muted-foreground text-center py-8">No community results</p>
                )}
                {results.communitySummaries.map((c) => (
                  <div
                    key={c.communityId}
                    className="bg-card border border-border rounded-xl overflow-hidden"
                  >
                    <button
                      onClick={() => toggleCommunity(c.communityId)}
                      className="w-full flex items-center justify-between p-4 text-left hover:bg-muted/30 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <Sparkles size={14} className="text-primary" />
                        <span className="text-xs font-medium text-foreground">
                          Community #{c.communityId}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          Level {c.level}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground">
                          {(c.relevanceScore * 100).toFixed(0)}%
                        </span>
                        <svg
                          width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                          strokeWidth="2"
                          className={cn(
                            "text-muted-foreground transition-transform",
                            expandedCommunities.has(c.communityId) && "rotate-180"
                          )}
                        >
                          <polyline points="6 9 12 15 18 9" />
                        </svg>
                      </div>
                    </button>
                    {expandedCommunities.has(c.communityId) && (
                      <div className="px-4 pb-4 space-y-2 border-t border-border pt-3">
                        <p className="text-xs text-secondary-foreground/70 leading-relaxed">
                          {c.summary}
                        </p>
                        {c.memberEntities.length > 0 && (
                          <div className="flex flex-wrap gap-1 pt-1">
                            {c.memberEntities.map((e: Record<string, unknown>, ei: number) => (
                              <span
                                key={ei}
                                className="bg-secondary text-secondary-foreground text-[10px] px-1.5 py-0.5 rounded-md"
                              >
                                {String(e.name || e.label || `Entity ${ei + 1}`)}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Source Attributions tab */}
            {activeTab === "attributions" && (
              <div className="space-y-2">
                {uniqueAttributions.length === 0 && (
                  <p className="text-xs text-muted-foreground text-center py-8">No source attributions</p>
                )}
                {uniqueAttributions.map((attr, i) => (
                  <div
                    key={i}
                    className="bg-card border border-border rounded-xl px-4 py-3 flex items-center gap-3"
                  >
                    <div className="w-7 h-7 rounded-lg bg-primary/5 flex items-center justify-center shrink-0">
                      <FileText size={12} className="text-primary" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs text-secondary-foreground truncate">{attr.fileName}</div>
                      <div className="text-[10px] text-muted-foreground">{attr.department}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {viewerDoc && (
        <FileViewer doc={viewerDoc} onClose={() => setViewerDoc(null)} />
      )}
    </div>
  );
}

/** Reusable card for a single chunk result with text highlighting */
function ChunkCard({
  chunk,
  searchQuery,
  onOpenFile,
}: {
  chunk: ChunkResult;
  searchQuery: string;
  onOpenFile: (chunk: ChunkResult) => void;
}) {
  const snippetText = chunk.text.length > 200 ? `${chunk.text.slice(0, 200)}…` : chunk.text;

  return (
    <div className="bg-card border border-border rounded-xl p-4 space-y-2">
      {/* Header: File name and Department */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <FileText size={14} className="text-primary shrink-0" />
          <button
            onClick={() => onOpenFile(chunk)}
            className="text-xs font-medium text-secondary-foreground hover:text-primary truncate"
            title={chunk.fileName}
          >
            {chunk.fileName}
          </button>
        </div>
        <span className="text-[10px] bg-secondary text-secondary-foreground px-2 py-0.5 rounded-md shrink-0">
          {chunk.department}
        </span>
      </div>

      {/* Relevance score bar */}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${Math.min(100, Math.round(chunk.score * 100))}%`,
              backgroundColor:
                chunk.score > 0.7
                  ? "#10b981"
                  : chunk.score > 0.4
                    ? "#f59e0b"
                    : "#8b949e",
            }}
          />
        </div>
        <span
          className="text-[10px] text-muted-foreground tabular-nums"
          title={`Raw score: ${chunk.score.toFixed(4)}`}
        >
          {(chunk.score * 100).toFixed(1)}%
        </span>
      </div>

      {/* Text snippet with highlighted matching text */}
      <p className="text-xs text-secondary-foreground/70 leading-relaxed line-clamp-3">
        {highlightText(snippetText, searchQuery)}
      </p>

      {/* Entities */}
      {chunk.entities.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-1">
          {chunk.entities.map((e: Record<string, unknown>, ei: number) => (
            <span
              key={ei}
              className="bg-primary/5 text-primary text-[10px] px-1.5 py-0.5 rounded-md"
            >
              {String(e.name || e.label || e.type || `Entity ${ei + 1}`)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default SearchResults;
