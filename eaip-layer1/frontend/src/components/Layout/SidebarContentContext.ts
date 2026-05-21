import { createContext, useContext } from "react";
import type { ReactNode } from "react";

type SetSidebarContent = (content: ReactNode) => void;

export const SidebarContentContext = createContext<SetSidebarContent>(() => {});

export function useSidebarContent() {
  return useContext(SidebarContentContext);
}
