import { useState, useCallback, useEffect, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { SearchResponse, SearchMode } from "../types";
import SearchResults from "../components/Search/SearchResults";
import { localSearch, globalSearch, combinedSearch } from "../api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
} from "@/components/ui/dropdown-menu";
import { Search, Loader2 } from "lucide-react";

export function SearchPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [lastSearchQuery, setLastSearchQuery] = useState("");
  const [lastSearchMode, setLastSearchMode] = useState<SearchMode>("combined");

  const [query, setQuery] = useState(searchParams.get("q") || "");
  const [mode, setMode] = useState<SearchMode>(
    (searchParams.get("mode") as SearchMode) || "combined"
  );

  const executeSearch = useCallback(async (q: string, m: SearchMode) => {
    setIsSearching(true);
    setLastSearchQuery(q);
    setLastSearchMode(m);
    try {
      let response: SearchResponse;
      if (m === "local") {
        response = await localSearch({ query: q });
      } else if (m === "global") {
        response = await globalSearch({ query: q });
      } else {
        response = await combinedSearch({ query: q });
      }
      setSearchResults(response);
    } catch {
      setSearchResults(null);
    } finally {
      setIsSearching(false);
    }
  }, []);

  // Execute search from URL query params
  useEffect(() => {
    const q = searchParams.get("q");
    const m = (searchParams.get("mode") as SearchMode) || "combined";
    if (q) {
      setQuery(q);
      setMode(m);
      executeSearch(q, m);
    }
  }, [searchParams, executeSearch]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      setSearchParams({ q: query.trim(), mode });
    }
  };

  const handleFileSelect = useCallback(
    (fileId: number) => {
      navigate(`/?fileId=${fileId}`);
    },
    [navigate]
  );

  return (
    <div className="flex flex-col h-full">
      {/* Search bar */}
      <div className="border-b border-border px-4 py-3 shrink-0">
        <form onSubmit={handleSubmit} className="flex items-center gap-2 max-w-2xl mx-auto">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="capitalize shrink-0 text-xs">
                {mode}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-72">
              <DropdownMenuRadioGroup
                value={mode}
                onValueChange={(v) => setMode(v as SearchMode)}
              >
                <DropdownMenuRadioItem value="local" className="items-start">
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium">Local</span>
                    <span className="text-xs text-muted-foreground font-normal">
                      Searches individual document chunks by semantic similarity. Best for finding specific passages or facts.
                    </span>
                  </div>
                </DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="global" className="items-start">
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium">Global</span>
                    <span className="text-xs text-muted-foreground font-normal">
                      Searches across community summaries for high-level themes and cross-document insights.
                    </span>
                  </div>
                </DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="combined" className="items-start">
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium">Combined</span>
                    <span className="text-xs text-muted-foreground font-normal">
                      Uses both local chunks and global summaries for comprehensive results. Recommended for most queries.
                    </span>
                  </div>
                </DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>

          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search documents..."
            className="flex-1"
          />

          <Button type="submit" size="sm" disabled={isSearching || !query.trim()}>
            {isSearching ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Search className="size-4" />
            )}
          </Button>
        </form>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-auto">
        <SearchResults
          results={searchResults}
          mode={lastSearchMode}
          isSearching={isSearching}
          query={lastSearchQuery}
          onFileSelect={handleFileSelect}
        />
      </div>
    </div>
  );
}

export default SearchPage;
