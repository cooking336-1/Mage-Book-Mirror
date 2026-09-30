"use client";

import { createContext, useContext, useState, useEffect, type ReactNode } from "react";

export type AppMode = "simple" | "full";

interface ModeContextValue {
  mode: AppMode;
  setMode: (m: AppMode) => void;
}

const ModeContext = createContext<ModeContextValue>({
  mode: "full",
  setMode: () => {},
});

export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<AppMode>("full");

  useEffect(() => {
    const saved = localStorage.getItem("mage-mode") as AppMode | null;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (saved === "simple" || saved === "full") setModeState(saved);
  }, []);

  const setMode = (m: AppMode) => {
    setModeState(m);
    localStorage.setItem("mage-mode", m);
  };

  return (
    <ModeContext.Provider value={{ mode, setMode }}>
      {children}
    </ModeContext.Provider>
  );
}

export function useMode() {
  return useContext(ModeContext);
}
