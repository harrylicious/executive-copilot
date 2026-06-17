import { Clock, Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import type { EmbeddingStatus } from "./hooks";

interface EmbeddingProgressBarProps {
  status: EmbeddingStatus | null;
  loading: boolean;
}

export function EmbeddingProgressBar({ status, loading }: EmbeddingProgressBarProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="bg-card border border-border rounded-xl p-4">
            <div className="h-4 w-16 bg-secondary rounded mb-2" />
            <div className="h-6 w-10 bg-secondary rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (!status) return null;

  const cards = [
    {
      label: "Pending",
      value: status.pending,
      icon: Clock,
      color: "#eab308",
      bgColor: "rgba(234, 179, 8, 0.1)",
    },
    {
      label: "Embedding",
      value: status.embedding,
      icon: Loader2,
      color: "#3b82f6",
      bgColor: "rgba(59, 130, 246, 0.1)",
    },
    {
      label: "Embedded",
      value: status.embedded,
      icon: CheckCircle2,
      color: "#10b981",
      bgColor: "rgba(16, 185, 129, 0.1)",
    },
    {
      label: "Failed",
      value: status.failed,
      icon: AlertTriangle,
      color: "#ef4444",
      bgColor: "rgba(239, 68, 68, 0.1)",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div key={card.label} className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: card.bgColor }}
            >
              <card.icon size={14} style={{ color: card.color }} />
            </div>
          </div>
          <div className="text-foreground text-xl font-light">{card.value}</div>
          <div className="text-muted-foreground text-xs mt-0.5">{card.label}</div>
        </div>
      ))}
    </div>
  );
}
