import { useCallback } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Settings2 } from "lucide-react";
import type { ChatConfig as ChatConfigType } from "@/types";

interface ChatConfigProps {
  config: ChatConfigType;
  onChange: (config: ChatConfigType) => void;
}

export function ChatConfig({ config, onChange }: ChatConfigProps) {
  const handleRetrievalModeChange = useCallback(
    (value: string) => {
      onChange({
        ...config,
        retrievalMode: value as ChatConfigType["retrievalMode"],
      });
    },
    [config, onChange]
  );

  const handleLanguageChange = useCallback(
    (value: string) => {
      onChange({
        ...config,
        language: value as ChatConfigType["language"],
      });
    },
    [config, onChange]
  );

  const handleTopKChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value;
      if (raw === "") {
        onChange({ ...config, topK: undefined });
        return;
      }
      const parsed = parseInt(raw, 10);
      if (!Number.isNaN(parsed) && parsed >= 1 && parsed <= 50) {
        onChange({ ...config, topK: parsed });
      }
    },
    [config, onChange]
  );

  const handleMaxTokensChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value;
      if (raw === "") {
        onChange({ ...config, maxTokens: undefined });
        return;
      }
      const parsed = parseInt(raw, 10);
      if (!Number.isNaN(parsed) && parsed >= 256 && parsed <= 16000) {
        onChange({ ...config, maxTokens: parsed });
      }
    },
    [config, onChange]
  );

  return (
    <div className="flex items-center gap-2">
      {/* Language selector */}
      <Select value={config.language} onValueChange={handleLanguageChange}>
        <SelectTrigger className="w-[90px] h-7 text-xs">
          <SelectValue placeholder="Lang" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="id">
            <div className="flex flex-col">
              <span>ID</span>
              <span className="text-[10px] text-muted-foreground font-normal">Indonesia</span>
            </div>
          </SelectItem>
          <SelectItem value="en">
            <div className="flex flex-col">
              <span>EN</span>
              <span className="text-[10px] text-muted-foreground font-normal">English</span>
            </div>
          </SelectItem>
        </SelectContent>
      </Select>

      {/* Retrieval mode - always visible */}
      <Select value={config.retrievalMode} onValueChange={handleRetrievalModeChange}>
        <SelectTrigger className="w-[100px] h-7 text-xs">
          <SelectValue placeholder="Mode" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="local">
            <div className="flex flex-col">
              <span>Local</span>
              <span className="text-[10px] text-muted-foreground font-normal">Chunk similarity</span>
            </div>
          </SelectItem>
          <SelectItem value="global">
            <div className="flex flex-col">
              <span>Global</span>
              <span className="text-[10px] text-muted-foreground font-normal">Community summaries</span>
            </div>
          </SelectItem>
          <SelectItem value="combined">
            <div className="flex flex-col">
              <span>Combined</span>
              <span className="text-[10px] text-muted-foreground font-normal">Both local + global</span>
            </div>
          </SelectItem>
        </SelectContent>
      </Select>

      {/* Advanced settings in dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label="Advanced settings">
            <Settings2 className="size-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-52 p-3">
          <DropdownMenuLabel className="text-xs px-0">Advanced</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <div className="space-y-3 pt-2">
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wide">
                Top K (1–50)
              </label>
              <Input
                type="number"
                min={1}
                max={50}
                placeholder="5"
                value={config.topK ?? ""}
                onChange={handleTopKChange}
                className="mt-1 h-7 text-xs"
              />
            </div>
            <div>
              <label className="text-[10px] text-muted-foreground uppercase tracking-wide">
                Max Tokens (256–16000)
              </label>
              <Input
                type="number"
                min={256}
                max={16000}
                placeholder="2048"
                value={config.maxTokens ?? ""}
                onChange={handleMaxTokensChange}
                className="mt-1 h-7 text-xs"
              />
            </div>
          </div>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
