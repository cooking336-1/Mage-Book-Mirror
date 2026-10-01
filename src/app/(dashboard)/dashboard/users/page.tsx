export default function UsersPage() {
  return (
    <div className="p-8 flex flex-col gap-6 pb-0">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[32px] font-bold text-[#191c1e] tracking-[-0.64px] leading-10">Users &amp; Access</h1>
          <p className="text-[#434655] text-base mt-1">Manage team members and their permissions.</p>
        </div>
        <button
          type="button"
          className="bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-sm font-medium px-4 h-10 rounded-lg shadow-sm transition-colors"
        >
          + Invite User
        </button>
      </div>

      <div className="bg-white border border-[#c3c6d7] rounded-xl p-12 text-center text-[#434655]">
        <p className="font-semibold text-[#141b2b] text-lg mb-1">No team members added</p>
        <p className="text-sm">Invite colleagues to collaborate on this account.</p>
      </div>
    </div>
  );
}
