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
        <div className="flex flex-col items-center gap-3 w-full max-w-md">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-32" />
          <div className="w-full space-y-3 mt-4">
            <Skeleton className="h-24 w-full rounded-xl" />
            <Skeleton className="h-24 w-full rounded-xl" />
            <Skeleton className="h-24 w-full rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  if (!results) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <div className="flex flex-col items-center gap-2">
          <svg className="w-12 h-12 text-muted-foreground/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <span className="text-sm">Enter a query to search the knowledge base</span>
        </div>
      </div>
    );
  }

  const { chunks, communitySummaries, entities, sourceAttributions, metadata } = results;
  const hasResults = chunks.length > 0 || communitySummaries.length > 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-4 py-2 border-b border-border bg-card">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-card-foreground">
              Results for &quot;{query}&quot;
            </span>
            <Badge variant="secondary" className="uppercase text-xs">
              {mode}
            </Badge>
          </div>
          <span className="text-xs text-muted-foreground">
            {metadata.queryTimeMs}ms &middot; {metadata.totalChunksSearched} chunks
          </span>
        </div>
        {!hasResults && (
          <p className="text-xs text-muted-foreground mt-1">No results found for this query.</p>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {sourceAttributions.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              Sources ({sourceAttributions.length})
            </h3>
            <div className="flex flex-wrap gap-2">
              {sourceAttributions.map((attr, i) => (
                <Button
                  key={i}
                  variant="ghost"
                  size="sm"
                  onClick={() => onFileSelect(attr.fileId as number)}
                  className="flex items-center gap-2 h-auto px-2 py-1"
                >
                  <span className="text-foreground truncate max-w-32 text-xs">
                    {attr.fileName as string}
                  </span>
                  <DepartmentBadge dept={attr.department as string} />
                </Button>
              ))}
            </div>
          </div>
        )}

        {chunks.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              Relevant Chunks ({chunks.length})
            </h3>
            <div className="space-y-2">
              {chunks.map((chunk, i) => (
                <Card
                  key={i}
                  className="p-0 gap-0 cursor-pointer hover:border-primary/50 transition-colors"
                  onClick={() => onFileSelect(chunk.fileId)}
                >
                  <CardHeader className="px-3 py-2 gap-0">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-sm font-medium text-card-foreground truncate">
                          {chunk.fileName}
                        </span>
                        <DepartmentBadge dept={chunk.department} />
                        <span className="text-xs text-muted-foreground">
                          chunk {chunk.chunkIndex}
                        </span>
                      </div>
                      <span className="text-xs font-mono text-primary shrink-0 ml-2">
                        {chunk.score.toFixed(3)}
                      </span>
                    </div>
                  </CardHeader>
                  <CardContent className="px-3 pb-2">
                    <p className="text-xs text-muted-foreground line-clamp-3 leading-relaxed">
                      {chunk.text}
                    </p>
                    {chunk.entities.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {chunk.entities.slice(0, 5).map((e, ei) => (
                          <Badge key={ei} variant="outline" className="rounded bg-accent/10 text-accent-foreground border-accent/30 text-[10px] px-1 py-0.5">
                            {e.name as string}
                          </Badge>
                        ))}
                        {chunk.entities.length > 5 && (
                          <span className="text-[10px] text-muted-foreground">
                            +{chunk.entities.length - 5} more
                          </span>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {communitySummaries.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              Community Summaries ({communitySummaries.length})
            </h3>
            <div className="space-y-2">
              {communitySummaries.map((cs, i) => (
                <Card key={i} className="p-0 gap-0">
                  <CardHeader className="px-3 py-2 gap-0">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-muted-foreground">
                        Level {cs.level} &middot; Community #{cs.communityId}
                      </span>
                      <span className="text-xs font-mono text-primary">
                        {cs.relevanceScore.toFixed(3)}
                      </span>
                    </div>
                  </CardHeader>
                  <CardContent className="px-3 pb-2">
                    <p className="text-xs text-muted-foreground line-clamp-4 leading-relaxed">
                      {cs.summary}
                    </p>
                    {cs.memberEntities.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {cs.memberEntities.slice(0, 8).map((e, ei) => (
                          <Badge key={ei} variant="outline" className="rounded bg-primary/10 text-primary border-primary/30 text-[10px] px-1 py-0.5">
                            {e.name as string}
                          </Badge>
                        ))}
                      </div>
                    )}
                    {cs.documentReferences.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {cs.documentReferences.map((ref, ri) => (
                          <Button
                            key={ri}
                            variant="ghost"
                            size="xs"
                            onClick={() => onFileSelect(ref.fileId as number)}
                            className="h-auto px-1.5 py-0.5 text-[10px] text-muted-foreground"
                          >
                            {ref.name as string}
                          </Button>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {entities.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              Entities ({entities.length})
            </h3>
            <div className="flex flex-wrap gap-1">
              {entities.map((e, i) => (
                <Badge
                  key={i}
                  variant="outline"
                  className="rounded bg-accent/10 text-accent-foreground border-accent/30 text-xs"
                >
                  {e.name as string}
                  <span className="text-[10px] text-muted-foreground ml-1">
                    ({e.type as string})
                  </span>
                </Badge>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SearchResults;
