"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/apiClient";
import { useIdleTimer } from "@/hooks/useIdleTimer";

interface Props {
  timeoutMs?: number; // Defaults to 15 * 60 * 1000 (15 minutes)
}

export default function IdleLockModal({ timeoutMs = 15 * 60 * 1000 }: Props) {
  const [isLocked, setIsLocked] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  // Attach idle timer; pauses when already locked
  useIdleTimer({
    timeoutMs,
    onIdle: () => {
      setIsLocked(true);
      setPassword("");
      setError(null);
    },
    enabled: !isLocked,
  });

  if (!isLocked) return null;

  const handleUnlock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password) {
      setError("Please enter your password.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await apiClient.post("/api/v1/auth/verify-password/", { password });
      setIsLocked(false);
      setPassword("");
      setError(null);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string; password?: string[] } } };
      const msg =
        axiosErr?.response?.data?.detail ||
        axiosErr?.response?.data?.password?.[0] ||
        "Incorrect password. Please try again.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiClient.post("/api/v1/auth/logout/");
    } catch {
      // Ignore network errors on logout
    } finally {
      router.push("/login");
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="idle-lock-title"
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-[#0f172a]/70 backdrop-blur-md p-4"
    >
      <div className="w-full max-w-md bg-white rounded-2xl border border-[#e2e8f0] shadow-2xl overflow-hidden p-8 text-center">
        {/* Shield / Lock Icon */}
        <div className="mx-auto w-16 h-16 bg-[#eff6ff] rounded-2xl flex items-center justify-center mb-6 shadow-inner">
          <svg
            className="w-8 h-8 text-[#2563eb]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
            />
          </svg>
        </div>

        <h2 id="idle-lock-title" className="text-2xl font-bold text-[#141b2b] tracking-tight">
          Session Locked
        </h2>
        <p className="text-sm text-[#64748b] mt-2 mb-6">
          For your financial security, your session was automatically locked after 15 minutes of
          inactivity. Enter your password to resume where you left off.
        </p>

        <form onSubmit={handleUnlock} className="space-y-4 text-left">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#475569] mb-1.5">
              Account Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••••••"
              autoFocus
              className={`w-full h-12 px-4 bg-[#f8fafc] border ${
                error
                  ? "border-red-400 focus:ring-red-400"
                  : "border-[#cbd5e1] focus:ring-[#2563eb]"
              } rounded-xl text-base text-[#1e293b] placeholder-[#94a3b8] focus:outline-none focus:ring-2`}
            />
            {error && <p className="text-xs text-red-600 mt-1.5 font-medium">{error}</p>}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full h-12 bg-[#2563eb] hover:bg-[#1d4ed8] text-white font-semibold rounded-xl transition duration-150 flex items-center justify-center space-x-2 shadow-sm disabled:opacity-50"
          >
            {loading ? <span>Verifying...</span> : <span>Unlock Session</span>}
          </button>
        </form>

        <div className="mt-6 pt-6 border-t border-[#f1f5f9]">
          <button
            type="button"
            onClick={handleLogout}
            className="text-xs text-[#64748b] hover:text-[#0f172a] font-medium transition"
          >
            Sign out or switch accounts &rarr;
          </button>
        </div>
      </div>
    </div>
  );
}
