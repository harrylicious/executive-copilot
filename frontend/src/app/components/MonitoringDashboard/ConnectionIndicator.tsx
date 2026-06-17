import { Wifi, WifiOff } from "lucide-react";
import type { ConnectionState } from "./hooks";

interface ConnectionIndicatorProps {
  connectionState: ConnectionState;
}

const stateConfig: Record<ConnectionState, { label: string; dotClass: string; icon: typeof Wifi }> = {
  connected: { label: "Connected", dotClass: "bg-green-500", icon: Wifi },
  connecting: { label: "Connecting...", dotClass: "bg-yellow-500 animate-pulse", icon: Wifi },
  reconnecting: { label: "Reconnecting...", dotClass: "bg-yellow-500 animate-pulse", icon: WifiOff },
  disconnected: { label: "Disconnected", dotClass: "bg-red-500", icon: WifiOff },
};

export function ConnectionIndicator({ connectionState }: ConnectionIndicatorProps) {
  const config = stateConfig[connectionState];
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-card border border-border text-xs">
      <span className={`w-2 h-2 rounded-full ${config.dotClass}`} />
      <Icon size={12} className="text-muted-foreground" />
      <span className="text-muted-foreground">{config.label}</span>
    </div>
  );
}
