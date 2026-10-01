"use client";

import { useEffect, useState, useMemo } from "react";
import { apiClient } from "@/lib/apiClient";
import {
  ShieldCheck,
  Search,
  RefreshCw,
  AlertCircle,
  Globe,
  Monitor,
  Clock,
  UserCheck,
} from "lucide-react";

interface AuditSecurityEntry {
  id: string;
  user_email: string | null;
  action: string;
  entity_type: string;
  ip_address: string | null;
  user_agent: string;
  sha256_hash: string;
  created_at: string;
}

function parseUserAgent(ua: string): string {
  if (!ua) return "Unknown Device";
  if (ua.includes("Windows")) return "Windows · Desktop";
  if (ua.includes("Macintosh")) return "macOS · Desktop";
  if (ua.includes("iPhone") || ua.includes("iPad")) return "iOS · Mobile";
  if (ua.includes("Android")) return "Android · Mobile";
  if (ua.includes("Linux")) return "Linux · System";
  return ua.slice(0, 30);
}

function formatRelativeTime(dateStr: string): string {
  try {
    const diffMs = Date.now() - new Date(dateStr).getTime();
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return "Just now";
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 30) return `${diffDays}d ago`;
    return new Date(dateStr).toLocaleDateString();
  } catch {
    return dateStr;
  }
}

export default function SecurityPage() {
  const [logs, setLogs] = useState<AuditSecurityEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [refreshIndex, setRefreshIndex] = useState(0);

  useEffect(() => {
    let isCancelled = false;

    apiClient
      .get<AuditSecurityEntry[]>("/api/v1/audit/trail/")
      .then((res) => {
        if (!isCancelled) {
          setLogs(res.data);
          setError(null);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          setError(err.response?.data?.detail || "Failed to load security logs.");
          setIsLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [refreshIndex]);

  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      const q = searchTerm.toLowerCase();
      return (
        log.action.toLowerCase().includes(q) ||
        (log.user_email && log.user_email.toLowerCase().includes(q)) ||
        (log.ip_address && log.ip_address.toLowerCase().includes(q)) ||
        log.entity_type.toLowerCase().includes(q)
      );
    });
  }, [logs, searchTerm]);

  const uniqueIPs = useMemo(() => {
    const ips = new Set(logs.map((l) => l.ip_address).filter(Boolean));
    return ips.size;
  }, [logs]);

  return (
    <div className="p-8 flex flex-col gap-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
              Security Log
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" />
              Live Audit Link
            </span>
          </div>
          <p className="text-[#434655] text-base mt-1">
            Monitor authentication activity, administrative actions, and IP access patterns.
          </p>
        </div>

        <button
          onClick={() => {
            setIsLoading(true);
            setRefreshIndex((prev) => prev + 1);
          }}
          disabled={isLoading}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#434655] bg-white border border-[#c3c6d7] rounded-lg hover:bg-slate-50 transition-colors shadow-sm disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <ShieldCheck className="w-4 h-4 text-blue-600" />
            Total Recorded Events
          </div>
          <p className="text-2xl font-bold text-[#191c1e] mt-2">{logs.length}</p>
          <p className="text-xs text-slate-500 mt-1">Immutable forensic audit entries</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <Globe className="w-4 h-4 text-emerald-600" />
            Unique Client IPs
          </div>
          <p className="text-2xl font-bold text-[#191c1e] mt-2">{uniqueIPs}</p>
          <p className="text-xs text-slate-500 mt-1">Monitored network origins</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <Clock className="w-4 h-4 text-amber-600" />
            Last Activity
          </div>
          <p className="text-2xl font-bold text-[#191c1e] mt-2">
            {logs.length > 0 ? formatRelativeTime(logs[0].created_at) : "N/A"}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            {logs.length > 0 ? new Date(logs[0].created_at).toLocaleTimeString() : "No events recorded"}
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by action, email, or IP..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-white border border-[#c3c6d7] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-slate-800 shadow-sm"
          />
        </div>
        <p className="text-xs text-slate-500 self-end sm:self-center">
          Showing <span className="font-semibold text-slate-700">{filteredLogs.length}</span> of{" "}
          <span className="font-semibold text-slate-700">{logs.length}</span> security events
        </p>
      </div>

      {/* Error Notice */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl flex items-center gap-3 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Events List */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-sm">
        <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f7f9fb] flex items-center justify-between">
          <p className="text-sm font-semibold text-[#434655]">Event Log</p>
          <span className="text-xs text-slate-500">Tamper-evident write-once</span>
        </div>

        {isLoading ? (
          <div className="p-12 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
            <p className="text-sm">Fetching security and access events...</p>
          </div>
        ) : filteredLogs.length === 0 ? (
          <div className="p-12 text-center text-slate-500 flex flex-col items-center justify-center gap-2">
            <ShieldCheck className="w-10 h-10 text-slate-300" />
            <p className="font-medium text-slate-700">No security events found</p>
            <p className="text-xs text-slate-400">
              {searchTerm ? "No events matched your search query." : "Authentication activity will be logged here."}
            </p>
          </div>
        ) : (
          filteredLogs.map((entry) => (
            <div
              key={entry.id}
              className="flex items-center gap-6 px-6 py-4 border-b border-[#e2e8f0] last:border-0 hover:bg-slate-50/70 transition-colors"
            >
              <div className="p-2.5 rounded-lg bg-blue-50 text-blue-700 flex-shrink-0">
                <UserCheck className="w-5 h-5" />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-semibold text-[#141b2b]">{entry.action}</p>
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-100 text-slate-600 border border-slate-200">
                    {entry.entity_type}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-[#434655] mt-1 flex-wrap">
                  <span className="flex items-center gap-1">
                    <Monitor className="w-3.5 h-3.5 text-slate-400" />
                    {parseUserAgent(entry.user_agent)}
                  </span>
                  <span>·</span>
                  <span className="flex items-center gap-1 font-mono">
                    <Globe className="w-3.5 h-3.5 text-slate-400" />
                    {entry.ip_address || "127.0.0.1"}
                  </span>
                  {entry.user_email && (
                    <>
                      <span>·</span>
                      <span className="text-slate-600">{entry.user_email}</span>
                    </>
                  )}
                </div>
              </div>

              <div className="text-right flex-shrink-0">
                <p className="text-xs font-medium text-slate-700 whitespace-nowrap">
                  {formatRelativeTime(entry.created_at)}
                </p>
                <p className="text-[10px] text-slate-400 mt-0.5 whitespace-nowrap">
                  {new Date(entry.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
