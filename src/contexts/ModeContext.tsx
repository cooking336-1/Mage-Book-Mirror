"use client";

import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import apiClient from "@/lib/apiClient";

export type AppMode = "simple" | "full" | "professional";

interface ModeContextValue {
  mode: AppMode;
  setMode: (m: AppMode) => void;
  isSyncing: boolean;
  isSimpleMode: boolean;
}

const ModeContext = createContext<ModeContextValue>({
  mode: "full",
  setMode: () => {},
  isSyncing: false,
  isSimpleMode: false,
});

export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<AppMode>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("mage-mode") as AppMode | null;
      if (saved === "simple" || saved === "full" || saved === "professional") return saved;
    }
    return "full";
  });
  const [isSyncing, setIsSyncing] = useState<boolean>(false);

  useEffect(() => {
    // Hydrate from backend active tenant record if session active
    let isCancelled = false;
    async function syncFromBackend() {
      try {
        const res = await apiClient.get<{ default_experience_mode?: string }>(
          "/api/v1/tenancy/organizations/current/"
        );
        const serverMode = res.data?.default_experience_mode;
        if (
          !isCancelled &&
          (serverMode === "simple" || serverMode === "full" || serverMode === "professional")
        ) {
          setModeState(serverMode);
          localStorage.setItem("mage-mode", serverMode);
        }
      } catch {
        // Fall back gracefully to local cached state if unauthenticated or offline
      }
    }

    syncFromBackend();
    return () => {
      isCancelled = true;
    };
  }, []);

  const setMode = (m: AppMode) => {
    setModeState(m);
    localStorage.setItem("mage-mode", m);

    // Asynchronously synchronize with backend tenant organization record
    setIsSyncing(true);
    const backendMode = m === "professional" ? "full" : m;
    apiClient
      .patch("/api/v1/tenancy/organizations/current/", {
        default_experience_mode: backendMode,
      })
      .catch((err) => {
        console.warn("Accounting mode synchronization deferred or failed:", err);
      })
      .finally(() => {
        setIsSyncing(false);
      });
  };

  const isSimpleMode = mode === "simple";

  return (
    <ModeContext.Provider value={{ mode, setMode, isSyncing, isSimpleMode }}>
      {children}
    </ModeContext.Provider>
  );
}

export function useMode() {
  return useContext(ModeContext);
}
