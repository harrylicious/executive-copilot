import { useState, useMemo } from "react";
import { X, Search, ChevronDown, ChevronUp, Sparkles } from "lucide-react";
import { ALL_TESTED_QUESTIONS, type TestedQuestion } from "../data/testedQuestions";

/* ---------- helpers ---------- */

const CATEGORY_LABELS: Record<string, string> = {
  "Factual Lookup": "Fakta",
  Filtering: "Filter",
  "Cross-Sheet": "Lintas Sheet",
  Calculation: "Kalkulasi",
  "Out-of-scope": "Out-of-scope",
  Aggregation: "Agregasi",
  Comparison: "Perbandingan",
};

const CATEGORY_ORDER = [
  "Factual Lookup",
  "Filtering",
  "Aggregation",
  "Comparison",
  "Calculation",
  "Cross-Sheet",
  "Out-of-scope",
];

const DIFFICULTY_COLORS: Record<string, string> = {
  easy: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  medium: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  hard: "bg-rose-500/10 text-rose-500 border-rose-500/20",
};

/* ---------- sub-components ---------- */

function QuestionCard({
  q,
  expanded,
  onToggle,
  onSend,
}: {
  q: TestedQuestion;
  expanded: boolean;
  onToggle: () => void;
  onSend: () => void;
}) {
  return (
    <div className="border border-border rounded-xl bg-card overflow-hidden transition-all hover:border-primary/30">
      {/* Header row */}
      <div className="flex items-start gap-3 px-4 py-3">
        <button onClick={onToggle} className="shrink-0 mt-0.5 text-muted-foreground hover:text-foreground transition-colors">
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-[11px] font-medium text-muted-foreground bg-secondary px-2 py-0.5 rounded-md border border-border">
              {CATEGORY_LABELS[q.category] || q.category}
            </span>
            <span className={`text-[11px] px-2 py-0.5 rounded-md border ${DIFFICULTY_COLORS[q.difficulty]}`}>
              {q.difficulty}
            </span>
            <span className="text-[11px] text-muted-foreground">#q{q.id}</span>
          </div>
          <p className="text-sm text-secondary-foreground leading-relaxed">{q.question}</p>

          {/* Answer (expanded) */}
          {expanded && (
            <div className="mt-3 pt-3 border-t border-border">
              <div className="flex items-start gap-2">
                <div className="w-5 h-5 rounded-md bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                  <Sparkles size={11} className="text-primary" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Expected Answer</p>
                  <p className="text-sm text-secondary-foreground leading-relaxed">{q.ground_truth}</p>
                </div>
              </div>
            </div>
          )}
        </div>
        <button
          onClick={onSend}
          className="shrink-0 px-3 py-1.5 text-xs font-medium bg-[#059669] hover:bg-[#047857] text-white rounded-lg transition-colors"
        >
          Tanya
        </button>
      </div>
    </div>
  );
}

/* ---------- main component ---------- */

interface Props {
  open: boolean;
  onClose: () => void;
  onSelectQuestion: (question: string) => void;
}

export function TestedQuestionsBrowser({ open, onClose, onSelectQuestion }: Props) {
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Collect unique categories in display order
  const categories = useMemo(() => {
    const seen = new Set<string>();
    return CATEGORY_ORDER.filter((c) => {
      if (seen.has(c)) return false;
      if (!ALL_TESTED_QUESTIONS.some((q) => q.category === c)) return false;
      seen.add(c);
      return true;
    });
  }, []);

  // Filter + search
  const filtered = useMemo(() => {
    let result = ALL_TESTED_QUESTIONS;
    if (selectedCategory) {
      result = result.filter((q) => q.category === selectedCategory);
    }
    if (search.trim()) {
      const term = search.toLowerCase();
      result = result.filter(
        (q) =>
          q.question.toLowerCase().includes(term) ||
          q.ground_truth.toLowerCase().includes(term) ||
          q.category.toLowerCase().includes(term)
      );
    }
    return result;
  }, [selectedCategory, search]);

  const handleSend = (q: TestedQuestion) => {
    onSelectQuestion(q.question);
    onClose();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border shrink-0">
          <div>
            <h3 className="text-foreground text-sm font-medium">Tested Questions</h3>
            <p className="text-muted-foreground text-xs mt-0.5">
              {ALL_TESTED_QUESTIONS.length} questions — klik untuk melihat jawaban yang diharapkan
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground p-1 rounded-lg hover:bg-secondary transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Search + filters */}
        <div className="p-4 border-b border-border space-y-3 shrink-0">
          {/* Search bar */}
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Cari pertanyaan atau jawaban..."
              className="w-full bg-input border border-border rounded-xl pl-9 pr-3 py-2 text-sm text-secondary-foreground placeholder-muted-foreground focus:outline-none focus:border-primary/50 transition-colors"
            />
          </div>
          {/* Category pills */}
          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => setSelectedCategory(null)}
              className={`px-2.5 py-1 text-xs rounded-lg border transition-colors ${
                !selectedCategory
                  ? "bg-[#059669] text-white border-[#059669]"
                  : "border-border text-muted-foreground hover:text-foreground hover:border-primary/30"
              }`}
            >
              All
            </button>
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
                className={`px-2.5 py-1 text-xs rounded-lg border transition-colors ${
                  selectedCategory === cat
                    ? "bg-[#059669] text-white border-[#059669]"
                    : "border-border text-muted-foreground hover:text-foreground hover:border-primary/30"
                }`}
              >
                {CATEGORY_LABELS[cat] || cat}
              </button>
            ))}
          </div>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <p className="text-muted-foreground text-sm">Tidak ada pertanyaan yang cocok</p>
              <p className="text-muted-foreground text-xs mt-1">Coba kata kunci lain</p>
            </div>
          ) : (
            filtered.map((q) => (
              <QuestionCard
                key={q.id}
                q={q}
                expanded={expandedId === q.id}
                onToggle={() => setExpandedId(expandedId === q.id ? null : q.id)}
                onSend={() => handleSend(q)}
              />
            ))
          )}
          <div className="h-2" />
        </div>
      </div>
    </div>
  );
}
