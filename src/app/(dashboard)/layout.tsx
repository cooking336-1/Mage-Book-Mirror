import DashboardFooter from "@/components/dashboard/DashboardFooter";
import IdleLockModal from "@/components/dashboard/IdleLockModal";
import SideNavBar from "@/components/dashboard/SideNavBar";
import TopNavBar from "@/components/dashboard/TopNavBar";
import { ModeProvider } from "@/contexts/ModeContext";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <ModeProvider>
      <div className="flex min-h-screen bg-[#f3f4f6]">
        <SideNavBar />
        <div className="flex-1 flex flex-col ml-64 min-w-0 min-h-screen">
          <TopNavBar />
          <main className="flex-1">{children}</main>
          <DashboardFooter />
        </div>
      </div>
      <IdleLockModal />
    </ModeProvider>
  );
}
