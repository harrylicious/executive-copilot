import { SearchResults } from "./search/SearchResults";

export function SearchPage() {
  return (
    <div className="flex flex-col h-full bg-background">
      <SearchResults />
    </div>
  );
}

export default SearchPage;
