import IdleLockModal from "@/components/dashboard/IdleLockModal";
import SideNavBar from "@/components/dashboard/SideNavBar";
import TopNavBar from "@/components/dashboard/TopNavBar";
import { ModeProvider } from "@/contexts/ModeContext";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModeProvider>
      <div className="flex min-h-screen bg-[#f3f4f6]">
        <SideNavBar />
        <div className="flex-1 flex flex-col ml-64 min-w-0">
          <TopNavBar />
          <main className="flex-1">{children}</main>
        </div>
      </div>
      <IdleLockModal />
    </ModeProvider>
  );
}
