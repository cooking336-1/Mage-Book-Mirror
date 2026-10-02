"use client";

import { useEffect, useState } from "react";
import { useMode } from "@/contexts/ModeContext";
import apiClient from "@/lib/apiClient";

interface AuditEntry {
  id: string;
  action: string;
  user_email: string | null;
  entity_type: string;
  entity_id: string;
  ip_address: string;
  sha256_hash: string;
  created_at: string;
  before_state?: Record<string, unknown> | null;
  after_state?: Record<string, unknown> | null;
}

export default function AuditPage() {
  const { mode } = useMode();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<AuditEntry | null>(null);

  const title = mode === "simple" ? "Activity Log" : "Audit Trail";
  const subtitle =
    mode === "simple"
      ? "A tamper-evident record of all activity and transactions in your account."
      : "Cryptographic SHA-256 audit trail compliant with statutory retention requirements.";

  const loadAuditTrail = () => {
    setIsLoading(true);
    setError(null);
    apiClient
      .get<AuditEntry[] | { results: AuditEntry[] }>("/api/v1/audit/trail/")
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : res.data.results || [];
        setEntries(list);
      })
      .catch((err: unknown) => {
        console.error("[AuditPage] Fetch error:", err);
        setError("Unable to load audit logs. Please verify permissions and try again.");
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    let isCancelled = false;
    apiClient
      .get<AuditEntry[] | { results: AuditEntry[] }>("/api/v1/audit/trail/")
      .then((res) => {
        if (!isCancelled) {
          const list = Array.isArray(res.data) ? res.data : res.data.results || [];
          setEntries(list);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          console.error("[AuditPage] Fetch error:", err);
          setError("Unable to load audit logs. Please verify permissions and try again.");
          setIsLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, []);

  const handleCopyHash = (hash: string, id: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(id);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const filtered = entries.filter((e) => {
    const q = search.toLowerCase();
    return (
      (e.action && e.action.toLowerCase().includes(q)) ||
      (e.user_email && e.user_email.toLowerCase().includes(q)) ||
      (e.entity_type && e.entity_type.toLowerCase().includes(q)) ||
      (e.sha256_hash && e.sha256_hash.toLowerCase().includes(q))
    );
  });

  const formatDate = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      {/* ── Page Header ────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
            {title}
          </h1>
          <p className="text-[#434655] text-base mt-1">{subtitle}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={loadAuditTrail}
            className="border border-[#c3c6d7] hover:bg-[#f1f3ff] text-[#141b2b] text-sm font-semibold px-4 h-10 rounded-lg transition-colors flex items-center gap-2"
          >
            <span>🔄</span> Refresh
          </button>
        </div>
      </div>

      {/* ── Error Banner ───────────────────────────────────────────── */}
      {error && (
        <div className="p-4 bg-[#fef2f2] border border-[#fecaca] rounded-xl flex items-center justify-between text-sm text-[#dc2626]">
          <span>{error}</span>
          <button
            type="button"
            onClick={loadAuditTrail}
            className="font-bold underline ml-4 hover:text-[#b91c1c]"
          >
            Retry
          </button>
        </div>
      )}

      {/* ── Search Bar ─────────────────────────────────────────────── */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl p-4 flex items-center justify-between gap-4">
        <div className="relative w-full sm:w-96">
          <input
            type="text"
            placeholder="Search by action, user email, or entity..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-10 pl-10 pr-4 text-sm bg-[#f8f9ff] border border-[#c3c6d7] rounded-lg focus:outline-none focus:border-[#2563eb] text-[#141b2b] placeholder-[#737687]"
          />
          <span className="absolute left-3 top-2.5 text-[#737687]">🔍</span>
        </div>
        <div className="text-xs text-[#64748b] hidden sm:block">
          Showing <span className="font-bold text-[#141b2b]">{filtered.length}</span> recorded events
        </div>
      </div>

      {/* ── Audit Entries Table ────────────────────────────────────── */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-[0px_1px_2px_rgba(0,0,0,0.04)]">
        <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f8f9ff] flex items-center justify-between">
          <p className="text-xs font-bold text-[#434655] uppercase tracking-wider">
            Immutable Audit Trail Logs
          </p>
          <span className="text-[11px] font-semibold text-[#059669] bg-[#ecfdf5] px-2.5 py-1 rounded-full border border-[#a7f3d0]">
            ✓ Tamper-Evident SHA-256 Chained
          </span>
        </div>

        {isLoading ? (
          <div className="py-16 text-center text-[#434655]">
            <p className="text-sm font-medium animate-pulse">Loading immutable audit logs...</p>
          </div>
        ) : filtered.length > 0 ? (
          <div className="divide-y divide-[#e2e8f0]">
            {filtered.map((entry) => (
              <div
                key={entry.id}
                className="p-5 sm:px-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 hover:bg-[#f8f9ff] transition-colors"
              >
                <div className="flex items-start gap-4 min-w-0">
                  <div className="w-9 h-9 rounded-full bg-[#dbeafe] flex items-center justify-center text-[#2563eb] text-sm font-bold shrink-0">
                    {entry.user_email ? entry.user_email[0].toUpperCase() : "S"}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm text-[#141b2b]">
                        {entry.user_email || "System Engine"}
                      </span>
                      {entry.entity_type && (
                        <span className="text-[10px] uppercase font-bold text-[#2563eb] bg-[#eff6ff] px-2 py-0.5 rounded border border-[#bfdbfe]">
                          {entry.entity_type}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-[#434655] mt-0.5">{entry.action}</p>
                    <div className="flex items-center gap-3 text-xs text-[#94a3b8] mt-1 flex-wrap">
                      <span>{formatDate(entry.created_at)}</span>
                      {entry.ip_address && (
                        <span>IP: {entry.ip_address}</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex sm:flex-col items-end gap-1.5 shrink-0 self-end sm:self-center">
                  {entry.sha256_hash && (
                    <button
                      type="button"
                      onClick={() => handleCopyHash(entry.sha256_hash, entry.id)}
                      title="Click to copy full SHA-256 hash"
                      className="font-mono text-[11px] bg-[#f1f3ff] hover:bg-[#e0e7ff] text-[#2563eb] px-2.5 py-1 rounded border border-[#c7d2fe] transition-colors flex items-center gap-1"
                    >
                      <span>🔒</span>
                      <span>{entry.sha256_hash.slice(0, 10)}...</span>
                      <span className="text-[10px] text-[#434655]">
                        {copiedHash === entry.id ? "✓ Copied" : "Copy"}
                      </span>
                    </button>
                  )}
                  {(entry.before_state || entry.after_state) && (
                    <button
                      type="button"
                      onClick={() => setSelectedEntry(entry)}
                      className="text-xs text-[#2563eb] font-semibold hover:underline mt-1"
                    >
                      View Diff &rarr;
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-16 text-center text-[#434655]">
            <p className="font-semibold text-[#141b2b] text-base mb-1">No audit events found</p>
            <p className="text-sm">Platform activities and financial postings will appear here.</p>
          </div>
        )}
      </div>

      {/* ── State Diff Modal ──────────────────────────────────────── */}
      {selectedEntry && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl shadow-xl border border-[#c3c6d7] max-w-xl w-full p-6 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-[#c3c6d7]">
              <div>
                <h3 className="font-bold text-[#141b2b]">Audit Event Inspection</h3>
                <p className="text-xs text-[#64748b]">{selectedEntry.action}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedEntry(null)}
                className="text-[#64748b] hover:text-[#141b2b] text-xl font-bold leading-none p-1"
              >
                &times;
              </button>
            </div>

            <div className="mt-4 flex flex-col gap-4 text-xs">
              <div>
                <p className="font-bold text-[#434655] uppercase mb-1">Cryptographic Hash</p>
                <div className="p-2 bg-[#f8f9ff] font-mono rounded border border-[#c3c6d7] break-all select-all">
                  {selectedEntry.sha256_hash}
                </div>
              </div>

              {selectedEntry.before_state && (
                <div>
                  <p className="font-bold text-[#dc2626] uppercase mb-1">State Before Change</p>
                  <pre className="p-3 bg-[#fef2f2] rounded border border-[#fecaca] overflow-x-auto text-[11px]">
                    {JSON.stringify(selectedEntry.before_state, null, 2)}
                  </pre>
                </div>
              )}

              {selectedEntry.after_state && (
                <div>
                  <p className="font-bold text-[#059669] uppercase mb-1">State After Change</p>
                  <pre className="p-3 bg-[#ecfdf5] rounded border border-[#a7f3d0] overflow-x-auto text-[11px]">
                    {JSON.stringify(selectedEntry.after_state, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            <div className="mt-6 pt-3 border-t border-[#c3c6d7] flex justify-end">
              <button
                type="button"
                onClick={() => setSelectedEntry(null)}
                className="px-4 py-2 bg-[#2563eb] text-white text-xs font-bold rounded-lg hover:bg-[#1d4ed8]"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
