import type { FC } from "react";
import { cn } from "@/lib/utils";
import {
  BarChart3,
  FileSearch,
  GitCompare,
  Lightbulb,
  ListChecks,
  TrendingUp,
} from "lucide-react";

interface PredefinedPromptsProps {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
  compact?: boolean;
}

const PROMPTS = [
  {
    icon: FileSearch,
    label: "Summarize documents",
    prompt: "Summarize the key information across all indexed documents. What are the main topics and themes?",
  },
  {
    icon: BarChart3,
    label: "Financial overview",
    prompt: "What financial data is available? Provide an overview of cashflow, budgets, and payment information.",
  },
  {
    icon: TrendingUp,
    label: "Demand forecast",
    prompt: "What are the latest demand forecasts and supply plans? Highlight any gaps or risks.",
  },
  {
    icon: GitCompare,
    label: "Cross-department links",
    prompt: "What are the relationships and dependencies between departments? Show how documents reference each other.",
  },
  {
    icon: ListChecks,
    label: "Compliance check",
    prompt: "Are there any policy documents or SOPs? Summarize the key compliance requirements and procedures.",
  },
  {
    icon: Lightbulb,
    label: "Key insights",
    prompt: "Based on all available data, what are the most important insights and action items for executive decision-making?",
  },
] as const;

export const PredefinedPrompts: FC<PredefinedPromptsProps> = ({
  onSelect,
  disabled,
  compact,
}) => {
  if (compact) {
    return (
      <div className="flex flex-wrap gap-1.5">
        {PROMPTS.map((item) => (
          <button
            key={item.label}
            onClick={() => onSelect(item.prompt)}
            disabled={disabled}
            className={cn(
              "inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs",
              "bg-muted text-muted-foreground hover:text-foreground hover:bg-muted/80",
              "transition-colors disabled:opacity-50 disabled:pointer-events-none"
            )}
          >
            <item.icon className="size-3" />
            {item.label}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-lg w-full">
      {PROMPTS.map((item) => (
        <button
          key={item.label}
          onClick={() => onSelect(item.prompt)}
          disabled={disabled}
          className={cn(
            "flex items-start gap-2.5 p-3 rounded-lg border border-border",
            "text-left text-sm transition-colors",
            "hover:bg-muted hover:border-primary/30",
            "disabled:opacity-50 disabled:pointer-events-none"
          )}
        >
          <item.icon className="size-4 text-primary shrink-0 mt-0.5" />
          <div>
            <span className="font-medium text-foreground text-xs">{item.label}</span>
            <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
              {item.prompt}
            </p>
          </div>
        </button>
      ))}
    </div>
  );
};
