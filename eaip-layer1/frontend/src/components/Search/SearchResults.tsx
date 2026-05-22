import type { FC } from "react";
import type { SearchResponse, SearchMode } from "../../types";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface SearchResultsProps {
  results: SearchResponse | null;
  mode: SearchMode;
  isSearching: boolean;
  query: string;
  onFileSelect: (fileId: number) => void;
}

const DepartmentBadge: FC<{ dept: string }> = ({ dept }) => {
  const colors: Record<string, string> = {
    demand_supply: "bg-purple-500/20 text-purple-400 border-purple-500/30",
    accounting_tax: "bg-teal-500/20 text-teal-400 border-teal-500/30",
    logistic: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    finance: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  };
  const color = colors[dept.toLowerCase()] || "bg-muted text-muted-foreground border-border";
  return (
    <Badge variant="outline" className={`rounded text-xs font-medium ${color}`}>
      {dept}
    </Badge>
  );
};

const ScoreBadge: FC<{ score: number }> = ({ score }) => {
  const pct = Math.round(score * 100);
  const color =
    pct >= 80 ? "text-green-400" : pct >= 60 ? "text-yellow-400" : "text-muted-foreground";
  return (
    <span className={`text-xs font-mono ${color}`} title={`Relevance score: ${score.toFixed(3)}`}>
      {pct}%
    </span>
  );
};

function highlightMatches(text: string, query: string): string {
  if (!query.trim()) return text;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`(${escaped})`, "gi");
  return text.replace(re, "<mark class=\"bg-yellow-300/30 text-foreground rounded-sm px-0.5\">$1</mark>");
}

const modeLabels: Record<SearchMode, string> = {
  local: "Local search — finds specific passages similar to your query",
  global: "Global search — finds high-level themes across document groups",
  combined: "Combined search — both specific passages and broad themes",
};

export const SearchResults: FC<SearchResultsProps> = ({
  results,
  mode,
  isSearching,
  query,
  onFileSelect,
}) => {
  if (isSearching) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-8">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-64" />
        <div className="w-full max-w-lg space-y-3 mt-4">
          <Skeleton className="h-28 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  if (!results) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4 max-w-sm text-center px-4">
          <div className="size-16 rounded-full bg-muted flex items-center justify-center">
            <svg className="w-8 h-8 text-muted-foreground/60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <div>
            <h3 className="text-base font-medium text-foreground mb-1">Search the knowledge base</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Enter a query above to find relevant documents, passages, and themes.
            </p>
          </div>
          <div className="flex flex-col gap-2 w-full text-left text-xs text-muted-foreground bg-muted/50 rounded-lg p-3">
            <p className="font-medium text-foreground/80">Search tips:</p>
            <ul className="space-y-1 list-disc pl-4">
              <li>Use specific terms for precise results</li>
              <li>Try different modes (Local / Global / Combined)</li>
              <li>Click a result to view the full document</li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  const { chunks, communitySummaries, entities, sourceAttributions, metadata } = results;
  const hasResults = chunks.length > 0 || communitySummaries.length > 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Results header */}
      <div className="px-4 py-3 border-b border-border bg-card space-y-1">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-sm font-medium text-card-foreground truncate">
              Results for &ldquo;{query}&rdquo;
            </span>
            <Badge variant="secondary" className="uppercase text-xs shrink-0">
              {mode}
            </Badge>
          </div>
          <span className="text-xs text-muted-foreground shrink-0 ml-2">
            {metadata.queryTimeMs}ms &middot; {metadata.totalChunksSearched} chunks searched
          </span>
        </div>
        <p className="text-xs text-muted-foreground">{modeLabels[mode]}</p>
        {!hasResults && (
          <p className="text-xs text-amber-400">No results found for this query. Try different keywords or search mode.</p>
        )}
      </div>

      {/* Results body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Source documents */}
        {sourceAttributions.length > 0 && (
          <section>
            <div className="mb-2">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Source documents ({sourceAttributions.length})
              </h3>
              <p className="text-xs text-muted-foreground/70 mt-0.5">
                Documents that matched your search. Click to open.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {sourceAttributions.map((attr, i) => (
                <Button
                  key={i}
                  variant="outline"
                  size="sm"
                  onClick={() => onFileSelect(attr.fileId as number)}
                  className="flex items-center gap-2 h-auto px-3 py-1.5 text-xs"
                >
                  <svg className="size-3.5 text-muted-foreground shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <span className="truncate max-w-36">{attr.fileName as string}</span>
                  <DepartmentBadge dept={attr.department as string} />
                </Button>
              ))}
            </div>
          </section>
        )}

        {/* Relevant chunks */}
        {chunks.length > 0 && (
          <section>
            <div className="mb-2">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Matching passages ({chunks.length})
              </h3>
              <p className="text-xs text-muted-foreground/70 mt-0.5">
                Specific passages from documents, ranked by relevance. Yellow highlights show where your query matched.
              </p>
            </div>
            <div className="space-y-2">
              {chunks.map((chunk, i) => (
                <Card
                  key={i}
                  className="p-0 gap-0 cursor-pointer hover:border-primary/50 transition-colors"
                  onClick={() => onFileSelect(chunk.fileId)}
                >
                  <CardHeader className="px-3 py-2 gap-0">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-sm font-medium text-card-foreground truncate">
                          {chunk.fileName}
                        </span>
                        <DepartmentBadge dept={chunk.department} />
                        <span className="text-xs text-muted-foreground shrink-0">
                          passage {chunk.chunkIndex}
                        </span>
                      </div>
                      <ScoreBadge score={chunk.score} />
                    </div>
                  </CardHeader>
                  <CardContent className="px-3 pb-2.5">
                    <p
                      className="text-xs text-muted-foreground line-clamp-3 leading-relaxed"
                      dangerouslySetInnerHTML={{
                        __html: highlightMatches(chunk.text, query),
                      }}
                    />
                    {chunk.entities.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {chunk.entities.slice(0, 5).map((e, ei) => (
                          <Badge key={ei} variant="outline" className="rounded bg-accent/10 text-accent-foreground border-accent/30 text-[10px] px-1.5 py-0.5">
                            {e.name as string}
                          </Badge>
                        ))}
                        {chunk.entities.length > 5 && (
                          <span className="text-[10px] text-muted-foreground self-center">
                            +{chunk.entities.length - 5}
                          </span>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        )}

        {/* Community summaries */}
        {communitySummaries.length > 0 && (
          <section>
            <div className="mb-2">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Community summaries ({communitySummaries.length})
              </h3>
              <p className="text-xs text-muted-foreground/70 mt-0.5">
                Thematic summaries from groups of related documents, useful for understanding broader context.
              </p>
            </div>
            <div className="space-y-2">
              {communitySummaries.map((cs, i) => (
                <Card key={i} className="p-0 gap-0">
                  <CardHeader className="px-3 py-2 gap-0">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-muted-foreground">
                        Theme summary &middot; Level {cs.level}
                      </span>
                      <ScoreBadge score={cs.relevanceScore} />
                    </div>
                  </CardHeader>
                  <CardContent className="px-3 pb-2.5 space-y-2">
                    <p
                      className="text-xs text-muted-foreground line-clamp-4 leading-relaxed"
                      dangerouslySetInnerHTML={{
                        __html: highlightMatches(cs.summary, query),
                      }}
                    />
                    {cs.memberEntities.length > 0 && (
                      <div>
                        <p className="text-[10px] text-muted-foreground/60 mb-1">Related entities</p>
                        <div className="flex flex-wrap gap-1">
                          {cs.memberEntities.slice(0, 8).map((e, ei) => (
                            <Badge key={ei} variant="outline" className="rounded bg-primary/10 text-primary border-primary/30 text-[10px] px-1.5 py-0.5">
                              {e.name as string}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {cs.documentReferences.length > 0 && (
                      <div>
                        <p className="text-[10px] text-muted-foreground/60 mb-1">Referenced documents</p>
                        <div className="flex flex-wrap gap-1">
                          {cs.documentReferences.map((ref, ri) => (
                            <Button
                              key={ri}
                              variant="ghost"
                              size="xs"
                              onClick={() => onFileSelect(ref.fileId as number)}
                              className="h-auto px-1.5 py-0.5 text-[10px] text-muted-foreground hover:text-foreground"
                            >
                              {ref.name as string}
                            </Button>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        )}

        {/* Entities */}
        {entities.length > 0 && (
          <section>
            <div className="mb-2">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Entities ({entities.length})
              </h3>
              <p className="text-xs text-muted-foreground/70 mt-0.5">
                Key people, organizations, and concepts found across the results.
              </p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {entities.map((e, i) => (
                <Badge
                  key={i}
                  variant="outline"
                  className="rounded bg-accent/10 text-accent-foreground border-accent/30 text-xs px-2 py-1"
                >
                  {e.name as string}
                  <span className="text-[10px] text-muted-foreground ml-1.5">
                    {e.type as string}
                  </span>
                </Badge>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
};

export default SearchResults;
