import { KnowledgeGraph } from "./graph/KnowledgeGraph";

export function GraphPage() {
  return (
    <div className="flex flex-col h-full bg-background">
      <div className="px-6 py-4 border-b border-border shrink-0">
        <h2 className="text-sm font-medium text-foreground">Knowledge Graph</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Visualize relationships between documents and entities
        </p>
      </div>
      <div className="flex-1 p-4 overflow-hidden">
        <KnowledgeGraph />
      </div>
    </div>
  );
}

export default GraphPage;
