"use client";

import { useEffect, useState, useMemo } from "react";
import { apiClient } from "@/lib/apiClient";
import {
  Users,
  UserPlus,
  Shield,
  Trash2,
  RefreshCw,
  Search,
  AlertCircle,
  CheckCircle,
  X,
  Clock,
  Lock,
} from "lucide-react";

interface TeamMember {
  id: string;
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: "OWNER" | "ADMIN" | "ACCOUNTANT" | "AUDITOR" | "BOOKKEEPER";
  is_active: boolean;
  access_expires_at: string | null;
  created_at: string;
}

const ROLE_CONFIG: Record<
  string,
  { label: string; badge: string; desc: string }
> = {
  OWNER: {
    label: "Organization Owner",
    badge: "bg-purple-100 text-purple-800 border-purple-200",
    desc: "Primary statutory authority. Non-demotable; controls settlement destinations.",
  },
  ADMIN: {
    label: "Administrator",
    badge: "bg-blue-100 text-blue-800 border-blue-200",
    desc: "Full management access across operations and team members.",
  },
  ACCOUNTANT: {
    label: "Accountant",
    badge: "bg-emerald-100 text-emerald-800 border-emerald-200",
    desc: "Can record journals, issue invoices, run payroll, and close periods.",
  },
  AUDITOR: {
    label: "Statutory Auditor",
    badge: "bg-amber-100 text-amber-800 border-amber-200",
    desc: "Read-only access to General Ledger, PBC packages, and immutable audit logs.",
  },
  BOOKKEEPER: {
    label: "Bookkeeper",
    badge: "bg-slate-100 text-slate-800 border-slate-200",
    desc: "Can record daily transactions and draft customer invoices.",
  },
};

export default function UsersPage() {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  // Invite Modal
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteFirstName, setInviteFirstName] = useState("");
  const [inviteLastName, setInviteLastName] = useState("");
  const [inviteRole, setInviteRole] = useState<TeamMember["role"]>("BOOKKEEPER");
  const [inviteExpiresAt, setInviteExpiresAt] = useState("");
  const [isInviting, setIsInviting] = useState(false);

  // Member to Delete
  const [memberToDelete, setMemberToDelete] = useState<TeamMember | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    apiClient
      .get<TeamMember[]>("/api/v1/tenancy/members/")
      .then((res) => {
        if (!isCancelled) {
          setMembers(res.data);
          setError(null);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          setError(err.response?.data?.detail || "Failed to load team members.");
          setIsLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [refreshKey]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail) return;

    setIsInviting(true);
    setError(null);
    setSuccessMsg(null);

    try {
      await apiClient.post("/api/v1/tenancy/members/", {
        email: inviteEmail.trim().toLowerCase(),
        first_name: inviteFirstName.trim(),
        last_name: inviteLastName.trim(),
        role: inviteRole,
        access_expires_at: inviteExpiresAt ? new Date(inviteExpiresAt).toISOString() : null,
      });

      setSuccessMsg(`Successfully invited ${inviteEmail}`);
      setIsInviteOpen(false);
      setInviteEmail("");
      setInviteFirstName("");
      setInviteLastName("");
      setInviteRole("BOOKKEEPER");
      setInviteExpiresAt("");
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to invite member. Please check permissions.");
    } finally {
      setIsInviting(false);
    }
  };

  const handleDeleteMember = async () => {
    if (!memberToDelete) return;
    setIsDeleting(true);
    setError(null);

    try {
      await apiClient.delete(`/api/v1/tenancy/members/${memberToDelete.id}/`);
      setSuccessMsg(`Removed ${memberToDelete.email} from organization.`);
      setMemberToDelete(null);
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to remove member.");
    } finally {
      setIsDeleting(false);
    }
  };

  const filteredMembers = useMemo(() => {
    return members.filter((m) => {
      const q = searchTerm.toLowerCase();
      const fullName = `${m.first_name} ${m.last_name}`.toLowerCase();
      return (
        m.email.toLowerCase().includes(q) ||
        fullName.includes(q) ||
        m.role.toLowerCase().includes(q)
      );
    });
  }, [members, searchTerm]);

  return (
    <div className="p-8 flex flex-col gap-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
              Users &amp; Access
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 flex items-center gap-1">
              <Shield className="w-3.5 h-3.5" />
              RBAC Governance
            </span>
          </div>
          <p className="text-[#434655] text-base mt-1">
            Manage team members, statutory external auditor access, and separation of duties.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setIsLoading(true);
              setRefreshKey((k) => k + 1);
            }}
            disabled={isLoading}
            className="p-2.5 text-slate-600 bg-white border border-[#c3c6d7] rounded-lg hover:bg-slate-50 transition-colors shadow-sm disabled:opacity-50"
            title="Refresh members"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-600" : ""}`} />
          </button>

          <button
            type="button"
            onClick={() => setIsInviteOpen(true)}
            className="inline-flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold px-4 h-10 rounded-lg shadow-sm transition-colors"
          >
            <UserPlus className="w-4 h-4" />
            + Invite User
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl flex items-center justify-between text-sm shadow-sm">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {successMsg && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 p-4 rounded-xl flex items-center justify-between text-sm shadow-sm">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-5 h-5 flex-shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Role Guide Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(ROLE_CONFIG)
          .filter(([role]) => role !== "OWNER")
          .map(([role, cfg]) => (
            <div key={role} className="bg-white border border-[#c3c6d7] rounded-xl p-4 shadow-sm">
              <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold border mb-2 ${cfg.badge}`}>
                {cfg.label}
              </span>
              <p className="text-xs text-slate-600 leading-relaxed">{cfg.desc}</p>
            </div>
          ))}
      </div>

      {/* Filter and Search */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by name, email, or role..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-white border border-[#c3c6d7] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-slate-800 shadow-sm"
          />
        </div>
        <p className="text-xs text-slate-500 self-end sm:self-center">
          Showing <span className="font-semibold text-slate-700">{filteredMembers.length}</span> of{" "}
          <span className="font-semibold text-slate-700">{members.length}</span> team members
        </p>
      </div>

      {/* Members Table */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-sm">
        <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f8fafc] flex items-center justify-between">
          <p className="text-sm font-bold text-[#141b2b]">Active Team &amp; Collaborators</p>
          <span className="text-xs text-slate-500">Dual-control authorization</span>
        </div>

        {isLoading ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
            <p className="text-sm">Loading organization members...</p>
          </div>
        ) : filteredMembers.length === 0 ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <Users className="w-12 h-12 text-slate-300" />
            <p className="font-bold text-slate-700 text-lg">No team members found</p>
            <p className="text-sm text-slate-400 max-w-sm">
              {searchTerm
                ? "No team member matched your search query."
                : "Invite colleagues, bookkeepers, or your external auditor to collaborate."}
            </p>
            {!searchTerm && (
              <button
                type="button"
                onClick={() => setIsInviteOpen(true)}
                className="mt-2 text-sm font-semibold text-blue-600 hover:underline"
              >
                + Invite your first member
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-6">Member</th>
                  <th className="py-3 px-6">Role</th>
                  <th className="py-3 px-6">Status</th>
                  <th className="py-3 px-6">Access Expiration</th>
                  <th className="py-3 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e2e8f0] text-sm">
                {filteredMembers.map((member) => {
                  const roleCfg = ROLE_CONFIG[member.role] || {
                    label: member.role,
                    badge: "bg-gray-100 text-gray-800 border-gray-200",
                  };
                  const isOwner = member.role === "OWNER";
                  const fullName = `${member.first_name || ""} ${member.last_name || ""}`.trim();

                  return (
                    <tr key={member.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-4 px-6">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-blue-100 text-blue-700 font-bold flex items-center justify-center text-xs shrink-0">
                            {member.first_name ? member.first_name[0].toUpperCase() : member.email[0].toUpperCase()}
                          </div>
                          <div>
                            <p className="font-semibold text-slate-900 leading-tight">
                              {fullName || "User"}
                            </p>
                            <p className="text-xs text-slate-500 mt-0.5">{member.email}</p>
                          </div>
                        </div>
                      </td>

                      <td className="py-4 px-6">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold border ${roleCfg.badge}`}
                        >
                          {roleCfg.label}
                        </span>
                      </td>

                      <td className="py-4 px-6">
                        {member.is_active ? (
                          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400">
                            <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />
                            Disabled
                          </span>
                        )}
                      </td>

                      <td className="py-4 px-6 text-xs text-slate-500">
                        {member.access_expires_at ? (
                          <span className="flex items-center gap-1 text-amber-700 font-medium">
                            <Clock className="w-3.5 h-3.5" />
                            {new Date(member.access_expires_at).toLocaleDateString()}
                          </span>
                        ) : (
                          <span className="text-slate-400">Permanent</span>
                        )}
                      </td>

                      <td className="py-4 px-6 text-right">
                        {isOwner ? (
                          <span
                            className="inline-flex items-center gap-1 text-xs text-slate-400 font-medium"
                            title="Owner role is immutable and cannot be revoked."
                          >
                            <Lock className="w-3.5 h-3.5" />
                            Protected
                          </span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setMemberToDelete(member)}
                            className="text-red-500 hover:text-red-700 p-1.5 rounded hover:bg-red-50 transition-colors"
                            title="Remove team member"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Invite Member Modal */}
      {isInviteOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-100 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-blue-600" />
                <h3 className="text-lg font-bold text-slate-900">Invite Team Member</h3>
              </div>
              <button
                onClick={() => setIsInviteOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleInvite} className="mt-4 flex flex-col gap-4">
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Email Address <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  required
                  placeholder="colleague@company.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    First Name
                  </label>
                  <input
                    type="text"
                    placeholder="Kwame"
                    value={inviteFirstName}
                    onChange={(e) => setInviteFirstName(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Last Name
                  </label>
                  <input
                    type="text"
                    placeholder="Mensah"
                    value={inviteLastName}
                    onChange={(e) => setInviteLastName(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Role &amp; Permissions <span className="text-red-500">*</span>
                </label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as TeamMember["role"])}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 bg-white"
                >
                  <option value="BOOKKEEPER">Bookkeeper (Invoicing &amp; basic entry)</option>
                  <option value="ACCOUNTANT">Accountant (Journals, reports, payroll)</option>
                  <option value="AUDITOR">Statutory Auditor (Read-only PBC packages)</option>
                  <option value="ADMIN">Administrator (Full operational access)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Access Expiration (Optional)
                </label>
                <input
                  type="date"
                  value={inviteExpiresAt}
                  onChange={(e) => setInviteExpiresAt(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Ideal for external statutory auditors who need temporary fiscal-year audit access.
                </p>
              </div>

              <div className="flex items-center justify-end gap-3 mt-4 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsInviteOpen(false)}
                  className="px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isInviting || !inviteEmail}
                  className="px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
                >
                  {isInviting && <RefreshCw className="w-4 h-4 animate-spin" />}
                  Send Invitation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Revoke Confirmation Modal */}
      {memberToDelete && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-100">
            <h3 className="text-lg font-bold text-slate-900">Revoke Team Access</h3>
            <p className="text-sm text-slate-600 mt-2">
              Are you sure you want to remove <span className="font-semibold text-slate-900">{memberToDelete.email}</span> from
              this organization? They will immediately lose access to all financial data.
            </p>

            <div className="flex items-center justify-end gap-3 mt-6">
              <button
                type="button"
                onClick={() => setMemberToDelete(null)}
                className="px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                Keep Member
              </button>
              <button
                type="button"
                onClick={handleDeleteMember}
                disabled={isDeleting}
                className="px-5 py-2 text-sm font-semibold text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
              >
                {isDeleting && <RefreshCw className="w-4 h-4 animate-spin" />}
                Revoke Access
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
