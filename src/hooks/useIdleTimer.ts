"use client";

import { useEffect, useRef } from "react";

interface UseIdleTimerOptions {
  timeoutMs?: number; // Default 15 minutes = 15 * 60 * 1000
  onIdle: () => void;
  enabled?: boolean;
}

/**
 * useIdleTimer
 *
 * Tracks user activity (mouse, keyboard, scroll, touch) and triggers `onIdle`
 * when no interaction occurs within the specified `timeoutMs` window.
 * Complies with financial application security specifications (15-min auto-lock).
 */
export function useIdleTimer({
  timeoutMs = 15 * 60 * 1000,
  onIdle,
  enabled = true,
}: UseIdleTimerOptions): void {
  const onIdleRef = useRef(onIdle);
  useEffect(() => {
    onIdleRef.current = onIdle;
  }, [onIdle]);

  useEffect(() => {
    if (!enabled) return;

    let timer: NodeJS.Timeout;

    const resetTimer = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        onIdleRef.current();
      }, timeoutMs);
    };

    const events = [
      "mousedown",
      "mousemove",
      "keydown",
      "scroll",
      "touchstart",
      "click",
    ];

    events.forEach(event => {
      window.addEventListener(event, resetTimer, { passive: true });
    });

    // Start timer on mount
    resetTimer();

    return () => {
      clearTimeout(timer);
      events.forEach(event => {
        window.removeEventListener(event, resetTimer);
      });
    };
  }, [timeoutMs, enabled]);
}
