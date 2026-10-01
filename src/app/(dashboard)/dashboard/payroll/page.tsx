"use client";

import { useEffect, useState, useMemo } from "react";
import { useMode } from "@/contexts/ModeContext";
import { apiClient } from "@/lib/apiClient";
import {
  Users,
  Plus,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  X,
  CreditCard,
  Building,
  KeyRound,
  Eye,
  Send,
  Smartphone,
  Check,
} from "lucide-react";

interface PayrollEmployeeItem {
  id: string;
  employee_name: string;
  employee_tin_or_ghana_card: string;
  momo_number: string;
  gross_salary: string | number;
  ssnit_employee: string | number;
  ssnit_employer: string | number;
  taxable_income: string | number;
  paye_tax: string | number;
  net_salary: string | number;
}

interface PayrollRun {
  id: string;
  period_id: string;
  period_name: string;
  maker_email: string;
  checker_email: string | null;
  status: "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "DISBURSED";
  total_gross_salary: string | number;
  total_ssnit_employee: string | number;
  total_ssnit_employer: string | number;
  total_paye_tax: string | number;
  total_net_payout: string | number;
  created_at: string;
  items?: PayrollEmployeeItem[];
}

interface FiscalPeriod {
  id: string;
  period_name: string;
  start_date: string;
  end_date: string;
  is_closed: boolean;
}

interface EmployeeFormInput {
  name: string;
  tin: string;
  momo: string;
  gross: string;
}

function formatGHS(amount: string | number): string {
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  return new Intl.NumberFormat("en-GH", {
    style: "currency",
    currency: "GHS",
    minimumFractionDigits: 2,
  })
    .format(isNaN(num) ? 0 : num)
    .replace("GHS", "GH¢");
}

export default function PayrollPage() {
  const { mode } = useMode();

  const [runs, setRuns] = useState<PayrollRun[]>([]);
  const [periods, setPeriods] = useState<FiscalPeriod[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // View details modal
  const [selectedRun, setSelectedRun] = useState<PayrollRun | null>(null);

  // Create Payroll Run Modal
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedPeriodId, setSelectedPeriodId] = useState("");
  const [employees, setEmployees] = useState<EmployeeFormInput[]>([
    { name: "", tin: "", momo: "", gross: "" },
  ]);
  const [isCreating, setIsCreating] = useState(false);

  // Approval TOTP Modal
  const [approvingRunId, setApprovingRunId] = useState<string | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [isApproving, setIsApproving] = useState(false);

  // Action busy indicators
  const [submittingRunId, setSubmittingRunId] = useState<string | null>(null);
  const [disbursingRunId, setDisbursingRunId] = useState<string | null>(null);

  useEffect(() => {
    let isCancelled = false;

    async function loadData() {
      try {
        const [runsRes, periodsRes] = await Promise.all([
          apiClient.get<PayrollRun[]>("/api/v1/payroll/runs/"),
          apiClient.get<FiscalPeriod[]>("/api/v1/ledger/fiscal-periods/"),
        ]);

        if (!isCancelled) {
          setRuns(runsRes.data);
          const activePeriods = periodsRes.data.filter((p) => !p.is_closed);
          setPeriods(activePeriods);
          if (activePeriods.length > 0 && !selectedPeriodId) {
            setSelectedPeriodId(activePeriods[0].id);
          }
          setError(null);
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (!isCancelled) {
          const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
          setError(resp?.detail || "Failed to load payroll runs.");
          setIsLoading(false);
        }
      }
    }

    loadData();

    return () => {
      isCancelled = true;
    };
  }, [refreshKey, selectedPeriodId]);

  // Aggregate Metrics
  const summaryMetrics = useMemo(() => {
    let gross = 0;
    let net = 0;
    let paye = 0;
    let ssnit = 0;

    runs.forEach((r) => {
      gross += parseFloat(String(r.total_gross_salary || 0));
      net += parseFloat(String(r.total_net_payout || 0));
      paye += parseFloat(String(r.total_paye_tax || 0));
      ssnit +=
        parseFloat(String(r.total_ssnit_employee || 0)) +
        parseFloat(String(r.total_ssnit_employer || 0));
    });

    return { gross, net, paye, ssnit };
  }, [runs]);

  // Handle Create Draft Run
  const handleCreateRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPeriodId) {
      setError("Please select an active fiscal period.");
      return;
    }

    const validEmployees = employees.filter(
      (emp) => emp.name.trim() && parseFloat(emp.gross) > 0
    );

    if (validEmployees.length === 0) {
      setError("Please add at least one employee with a valid gross salary.");
      return;
    }

    setIsCreating(true);
    setError(null);

    try {
      await apiClient.post("/api/v1/payroll/runs/", {
        period_id: selectedPeriodId,
        employees: validEmployees.map((emp) => ({
          employee_name: emp.name.trim(),
          gross_salary: parseFloat(emp.gross),
          employee_tin_or_ghana_card: emp.tin.trim(),
          momo_number: emp.momo.trim(),
        })),
      });

      setSuccessMsg("Payroll run drafted with Ghanaian statutory deductions.");
      setIsCreateOpen(false);
      setEmployees([{ name: "", tin: "", momo: "", gross: "" }]);
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to draft payroll run.");
    } finally {
      setIsCreating(false);
    }
  };

  // Handle Submit for Review
  const handleSubmitRun = async (runId: string) => {
    setSubmittingRunId(runId);
    setError(null);

    try {
      await apiClient.post(`/api/v1/payroll/runs/${runId}/submit/`);
      setSuccessMsg("Payroll run submitted for checker review and TOTP approval.");
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to submit payroll run.");
    } finally {
      setSubmittingRunId(null);
    }
  };

  // Handle TOTP Approval
  const handleApproveRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!approvingRunId || !totpCode) return;

    setIsApproving(true);
    setError(null);

    try {
      await apiClient.post(`/api/v1/payroll/runs/${approvingRunId}/approve/`, {
        totp_code: totpCode.trim(),
      });

      setSuccessMsg("Payroll run verified and approved with 2FA step-up.");
      setApprovingRunId(null);
      setTotpCode("");
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "2FA verification failed. Please check your authenticator code.");
    } finally {
      setIsApproving(false);
    }
  };

  // Handle MoMo Disbursement
  const handleDisburseRun = async (runId: string) => {
    setDisbursingRunId(runId);
    setError(null);

    try {
      await apiClient.post(`/api/v1/payroll/runs/${runId}/disburse/`);
      setSuccessMsg("Payroll run disbursed and general ledger entry posted!");
      setRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string } } }).response?.data;
      setError(resp?.detail || "Failed to disburse payroll.");
    } finally {
      setDisbursingRunId(null);
    }
  };

  const getStatusBadge = (status: PayrollRun["status"]) => {
    switch (status) {
      case "DRAFT":
        return "bg-slate-100 text-slate-700 border-slate-200";
      case "PENDING_APPROVAL":
        return "bg-amber-100 text-amber-800 border-amber-200";
      case "APPROVED":
        return "bg-blue-100 text-blue-800 border-blue-200";
      case "DISBURSED":
        return "bg-emerald-100 text-emerald-800 border-emerald-200";
      default:
        return "bg-gray-100 text-gray-700 border-gray-200";
    }
  };

  return (
    <div className="p-8 flex flex-col gap-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">
              {mode === "simple" ? "Pay Staff" : "Payroll Management"}
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
              <Check className="w-3.5 h-3.5" />
              Ghana Act 1151 Compliant
            </span>
          </div>
          <p className="text-[#434655] text-base mt-1">
            {mode === "simple"
              ? "Calculate staff wages, Ghana PAYE taxes, and Mobile Money payouts."
              : "GRA PAYE progressive tax, SSNIT Tier 1/2 calculations, and maker-checker disbursements."}
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
            title="Refresh payroll data"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-600" : ""}`} />
          </button>

          <button
            type="button"
            onClick={() => setIsCreateOpen(true)}
            className="inline-flex items-center gap-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-semibold px-4 h-10 rounded-lg shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            {mode === "simple" ? "+ Pay Staff Member" : "+ New Payroll Run"}
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

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <Building className="w-4 h-4 text-blue-600" />
            Total Gross Pay
          </div>
          <p className="text-2xl font-bold text-[#191c1e] mt-2">{formatGHS(summaryMetrics.gross)}</p>
          <p className="text-xs text-slate-500 mt-1">Pre-deduction wage base</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <CreditCard className="w-4 h-4 text-emerald-600" />
            Total Net Payout
          </div>
          <p className="text-2xl font-bold text-emerald-700 mt-2">{formatGHS(summaryMetrics.net)}</p>
          <p className="text-xs text-slate-500 mt-1">Disbursed to staff &amp; MoMo</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <Smartphone className="w-4 h-4 text-amber-600" />
            GRA PAYE Withheld
          </div>
          <p className="text-2xl font-bold text-[#191c1e] mt-2">{formatGHS(summaryMetrics.paye)}</p>
          <p className="text-xs text-slate-500 mt-1">Statutory income tax liability</p>
        </div>

        <div className="bg-white border border-[#c3c6d7] rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500 tracking-wider">
            <Users className="w-4 h-4 text-indigo-600" />
            SSNIT (Tier 1 &amp; 2)
          </div>
          <p className="text-2xl font-bold text-[#191c1e] mt-2">{formatGHS(summaryMetrics.ssnit)}</p>
          <p className="text-xs text-slate-500 mt-1">Employee 5.5% + Employer 13%</p>
        </div>
      </div>

      {/* Payroll Runs Table */}
      <div className="bg-white border border-[#c3c6d7] rounded-xl overflow-hidden shadow-sm">
        <div className="border-b border-[#c3c6d7] px-6 py-4 bg-[#f8fafc] flex items-center justify-between">
          <p className="text-sm font-bold text-[#141b2b]">Statutory Payroll Runs</p>
          <span className="text-xs text-slate-500">Dual-control maker-checker workflow</span>
        </div>

        {isLoading ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
            <p className="text-sm">Loading payroll records...</p>
          </div>
        ) : runs.length === 0 ? (
          <div className="p-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3">
            <Users className="w-12 h-12 text-slate-300" />
            <p className="font-bold text-slate-700 text-lg">No payroll runs recorded</p>
            <p className="text-sm text-slate-400 max-w-sm">
              Create your first payroll run to calculate Ghana PAYE and SSNIT statutory deductions.
            </p>
            <button
              type="button"
              onClick={() => setIsCreateOpen(true)}
              className="mt-2 text-sm font-semibold text-blue-600 hover:underline"
            >
              + Create draft payroll run
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-6">Period</th>
                  <th className="py-3 px-6">Status</th>
                  <th className="py-3 px-6">Gross Pay</th>
                  <th className="py-3 px-6">GRA PAYE</th>
                  <th className="py-3 px-6">Net Payout</th>
                  <th className="py-3 px-6">Maker / Checker</th>
                  <th className="py-3 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e2e8f0] text-sm">
                {runs.map((run) => (
                  <tr key={run.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-4 px-6 font-semibold text-slate-900">
                      <div>{run.period_name || "Current Period"}</div>
                      <div className="text-xs text-slate-400 font-normal mt-0.5">
                        {new Date(run.created_at).toLocaleDateString()}
                      </div>
                    </td>

                    <td className="py-4 px-6">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-bold border ${getStatusBadge(
                          run.status
                        )}`}
                      >
                        {run.status.replace(/_/g, " ")}
                      </span>
                    </td>

                    <td className="py-4 px-6 font-mono text-slate-800">
                      {formatGHS(run.total_gross_salary)}
                    </td>

                    <td className="py-4 px-6 font-mono text-amber-700">
                      {formatGHS(run.total_paye_tax)}
                    </td>

                    <td className="py-4 px-6 font-mono font-bold text-emerald-700">
                      {formatGHS(run.total_net_payout)}
                    </td>

                    <td className="py-4 px-6 text-xs text-slate-600">
                      <div>
                        <span className="font-semibold">Maker:</span> {run.maker_email}
                      </div>
                      {run.checker_email && (
                        <div className="text-slate-500 mt-0.5">
                          <span className="font-semibold">Checker:</span> {run.checker_email}
                        </div>
                      )}
                    </td>

                    <td className="py-4 px-6 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {/* View Details */}
                        <button
                          type="button"
                          onClick={() => setSelectedRun(run)}
                          className="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                          title="View Employee Breakdown"
                        >
                          <Eye className="w-4 h-4" />
                        </button>

                        {/* Maker: Submit */}
                        {run.status === "DRAFT" && (
                          <button
                            type="button"
                            onClick={() => handleSubmitRun(run.id)}
                            disabled={submittingRunId === run.id}
                            className="inline-flex items-center gap-1.5 px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded text-xs font-semibold shadow-sm transition-colors disabled:opacity-50"
                          >
                            {submittingRunId === run.id ? (
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Send className="w-3.5 h-3.5" />
                            )}
                            Submit
                          </button>
                        )}

                        {/* Checker: 2FA Approve */}
                        {run.status === "PENDING_APPROVAL" && (
                          <button
                            type="button"
                            onClick={() => setApprovingRunId(run.id)}
                            className="inline-flex items-center gap-1.5 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-semibold shadow-sm transition-colors"
                          >
                            <KeyRound className="w-3.5 h-3.5" />
                            2FA Approve
                          </button>
                        )}

                        {/* Owner/Admin: Disburse */}
                        {run.status === "APPROVED" && (
                          <button
                            type="button"
                            onClick={() => handleDisburseRun(run.id)}
                            disabled={disbursingRunId === run.id}
                            className="inline-flex items-center gap-1.5 px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-xs font-semibold shadow-sm transition-colors disabled:opacity-50"
                          >
                            {disbursingRunId === run.id ? (
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <CreditCard className="w-3.5 h-3.5" />
                            )}
                            Disburse
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create Payroll Run Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-3xl w-full p-6 shadow-2xl border border-slate-100 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Users className="w-5 h-5 text-blue-600" />
                <h3 className="text-lg font-bold text-slate-900">
                  {mode === "simple" ? "Pay Staff" : "Draft Statutory Payroll Run"}
                </h3>
              </div>
              <button
                onClick={() => setIsCreateOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateRun} className="mt-4 flex flex-col gap-5">
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Active Fiscal Period <span className="text-red-500">*</span>
                </label>
                <select
                  value={selectedPeriodId}
                  onChange={(e) => setSelectedPeriodId(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-600"
                >
                  {periods.length === 0 ? (
                    <option value="">No open fiscal periods found</option>
                  ) : (
                    periods.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.period_name} ({p.start_date} to {p.end_date})
                      </option>
                    ))
                  )}
                </select>
              </div>

              {/* Employee Rows */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-xs font-bold uppercase text-slate-600">
                    Employees &amp; Salaries
                  </label>
                  <button
                    type="button"
                    onClick={() =>
                      setEmployees([...employees, { name: "", tin: "", momo: "", gross: "" }])
                    }
                    className="text-xs font-bold text-blue-600 hover:underline flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add Another Employee
                  </button>
                </div>

                <div className="flex flex-col gap-3">
                  {employees.map((emp, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-slate-50 border border-slate-200 rounded-lg grid grid-cols-1 sm:grid-cols-4 gap-3 items-end"
                    >
                      <div>
                        <label className="block text-[11px] font-semibold text-slate-500 mb-0.5">
                          Full Name *
                        </label>
                        <input
                          type="text"
                          required
                          placeholder="e.g. Kwame Mensah"
                          value={emp.name}
                          onChange={(e) => {
                            const updated = [...employees];
                            updated[idx].name = e.target.value;
                            setEmployees(updated);
                          }}
                          className="w-full px-2.5 py-1.5 border border-slate-300 rounded text-sm bg-white"
                        />
                      </div>

                      <div>
                        <label className="block text-[11px] font-semibold text-slate-500 mb-0.5">
                          Ghana Card / TIN
                        </label>
                        <input
                          type="text"
                          placeholder="GHA-123456789-0"
                          value={emp.tin}
                          onChange={(e) => {
                            const updated = [...employees];
                            updated[idx].tin = e.target.value;
                            setEmployees(updated);
                          }}
                          className="w-full px-2.5 py-1.5 border border-slate-300 rounded text-sm bg-white"
                        />
                      </div>

                      <div>
                        <label className="block text-[11px] font-semibold text-slate-500 mb-0.5">
                          MoMo Number
                        </label>
                        <input
                          type="text"
                          placeholder="024XXXXXXX"
                          value={emp.momo}
                          onChange={(e) => {
                            const updated = [...employees];
                            updated[idx].momo = e.target.value;
                            setEmployees(updated);
                          }}
                          className="w-full px-2.5 py-1.5 border border-slate-300 rounded text-sm bg-white"
                        />
                      </div>

                      <div className="flex items-center gap-2">
                        <div className="flex-1">
                          <label className="block text-[11px] font-semibold text-slate-500 mb-0.5">
                            Gross Pay (GH¢) *
                          </label>
                          <input
                            type="number"
                            step="0.01"
                            min="0.01"
                            required
                            placeholder="3500.00"
                            value={emp.gross}
                            onChange={(e) => {
                              const updated = [...employees];
                              updated[idx].gross = e.target.value;
                              setEmployees(updated);
                            }}
                            className="w-full px-2.5 py-1.5 border border-slate-300 rounded text-sm bg-white font-mono"
                          />
                        </div>
                        {employees.length > 1 && (
                          <button
                            type="button"
                            onClick={() => {
                              setEmployees(employees.filter((_, i) => i !== idx));
                            }}
                            className="p-2 text-red-500 hover:text-red-700 self-end"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 mt-4 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating}
                  className="px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
                >
                  {isCreating && <RefreshCw className="w-4 h-4 animate-spin" />}
                  Compile &amp; Save Draft
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* TOTP Step-Up 2FA Modal */}
      {approvingRunId && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-100">
            <div className="flex items-center gap-3 pb-3 border-b border-slate-100">
              <div className="p-2 rounded-lg bg-blue-50 text-blue-700">
                <KeyRound className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900">Step-Up 2FA Approval</h3>
                <p className="text-xs text-slate-500">Maker-Checker authorization requirement</p>
              </div>
            </div>

            <form onSubmit={handleApproveRun} className="mt-4 flex flex-col gap-4">
              <p className="text-sm text-slate-600">
                Enter the 6-digit verification code from your authenticator app to authorize this
                statutory payroll disbursement.
              </p>

              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  6-Digit TOTP Code
                </label>
                <input
                  type="text"
                  maxLength={6}
                  required
                  placeholder="123456"
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-center tracking-widest text-xl font-mono focus:outline-none focus:ring-2 focus:ring-blue-600"
                />
              </div>

              <div className="flex items-center justify-end gap-3 mt-2">
                <button
                  type="button"
                  onClick={() => {
                    setApprovingRunId(null);
                    setTotpCode("");
                  }}
                  className="px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isApproving || totpCode.length !== 6}
                  className="px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
                >
                  {isApproving && <RefreshCw className="w-4 h-4 animate-spin" />}
                  Verify &amp; Approve
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* View Breakdown Drawer / Modal */}
      {selectedRun && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-4xl w-full p-6 shadow-2xl border border-slate-100 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div>
                <h3 className="text-lg font-bold text-slate-900">
                  Payroll Run Details: {selectedRun.period_name}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Created {new Date(selectedRun.created_at).toLocaleString()} by{" "}
                  {selectedRun.maker_email}
                </p>
              </div>
              <button
                onClick={() => setSelectedRun(null)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 uppercase text-slate-500 font-bold">
                    <th className="py-2.5 px-3">Employee</th>
                    <th className="py-2.5 px-3">Gross</th>
                    <th className="py-2.5 px-3">SSNIT EE (5.5%)</th>
                    <th className="py-2.5 px-3">SSNIT ER (13%)</th>
                    <th className="py-2.5 px-3">Taxable</th>
                    <th className="py-2.5 px-3">PAYE Tax</th>
                    <th className="py-2.5 px-3 text-right">Net Payout</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {selectedRun.items && selectedRun.items.length > 0 ? (
                    selectedRun.items.map((it) => (
                      <tr key={it.id} className="hover:bg-slate-50">
                        <td className="py-3 px-3">
                          <p className="font-semibold text-slate-900">{it.employee_name}</p>
                          <p className="text-[11px] text-slate-400">
                            {it.employee_tin_or_ghana_card || "No TIN"} · {it.momo_number || "No MoMo"}
                          </p>
                        </td>
                        <td className="py-3 px-3 font-mono">{formatGHS(it.gross_salary)}</td>
                        <td className="py-3 px-3 font-mono text-slate-600">
                          {formatGHS(it.ssnit_employee)}
                        </td>
                        <td className="py-3 px-3 font-mono text-slate-600">
                          {formatGHS(it.ssnit_employer)}
                        </td>
                        <td className="py-3 px-3 font-mono text-slate-600">
                          {formatGHS(it.taxable_income)}
                        </td>
                        <td className="py-3 px-3 font-mono text-amber-700 font-medium">
                          {formatGHS(it.paye_tax)}
                        </td>
                        <td className="py-3 px-3 font-mono text-right font-bold text-emerald-700">
                          {formatGHS(it.net_salary)}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400">
                        No employee line item details returned for this run.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="flex justify-end mt-4 pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setSelectedRun(null)}
                className="px-5 py-2 text-sm font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
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
