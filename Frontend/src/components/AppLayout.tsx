import { ReactNode, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Activity, LayoutDashboard, Users, FolderSearch, LogOut, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";

const navItems = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/patients", label: "Patients", icon: Users },
  { path: "/history", label: "Case History", icon: FolderSearch },
];

export default function AppLayout({ children }: { children: ReactNode }) {
  const { doctor, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [logoError, setLogoError] = useState(false);
  const visibleNavItems = isAdmin ? navItems.filter((item) => item.path === "/dashboard") : navItems;

  return (
    <div className="min-h-screen bg-medical-bg">
      {/* Top Nav */}
      <header className="sticky top-0 z-50 border-b border-white/50 bg-background/70 backdrop-blur-xl shadow-[0_12px_30px_-24px_rgba(15,23,42,0.6)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate("/dashboard")}>
            {logoError ? (
              <div className="p-1.5 rounded-lg medical-gradient">
                <Activity className="w-5 h-5 text-primary-foreground" />
              </div>
            ) : (
              <img
                src="/favicon.ico"
                alt="DermAI logo"
                className="w-8 h-8 rounded-xl border border-white/60 bg-card/80 object-contain shadow-sm"
                onError={() => setLogoError(true)}
              />
            )}
            <span className="font-semibold text-lg tracking-tight text-foreground hidden sm:block">DermAI CDSS</span>
          </div>

          <nav className="flex items-center gap-1">
            {isAdmin && (
              <Button variant={location.pathname === "/admin" ? "secondary" : "ghost"} size="sm" onClick={() => navigate("/admin")} className="gap-1.5">
                <Shield className="w-4 h-4" /> Admin
              </Button>
            )}
            {visibleNavItems.map((item) => (
              <Button key={item.path} variant={location.pathname === item.path ? "secondary" : "ghost"} size="sm" onClick={() => navigate(item.path)} className="gap-1.5">
                <item.icon className="w-4 h-4" />
                <span className="hidden sm:inline">{item.label}</span>
              </Button>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground hidden md:block">{doctor?.name}</span>
            <Button variant="ghost" size="sm" onClick={() => { logout(); navigate("/"); }} className="gap-1.5 text-destructive hover:text-destructive">
              <LogOut className="w-4 h-4" /> <span className="hidden sm:inline">Logout</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">{children}</main>
    </div>
  );
}
