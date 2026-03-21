"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useLocale } from "@/lib/i18n";
import LanguageSwitcher from "@/components/language-switcher";
import {
  LayoutDashboard,
  Users,
  Building2,
  UserCircle,
  FileText,
  CheckSquare,
  LogOut,
  Bell,
  BarChart3,
  FileCode2,
  BellRing,
  ScrollText,
  Shield,
  Settings,
  Search,
  Menu,
  X,
  type LucideIcon,
} from "lucide-react";

interface NavItem {
  href: string;
  labelKey: string;
  icon: LucideIcon;
}

interface NavSection {
  titleKey: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    titleKey: "nav.sectionMain",
    items: [
      { href: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
    ],
  },
  {
    titleKey: "nav.sectionBusiness",
    items: [
      { href: "/dashboard/events", labelKey: "nav.events", icon: Bell },
      { href: "/dashboard/clients", labelKey: "nav.clients", icon: UserCircle },
      { href: "/dashboard/action-items", labelKey: "nav.actionItems", icon: CheckSquare },
      { href: "/dashboard/analytics", labelKey: "nav.analytics", icon: BarChart3 },
    ],
  },
  {
    titleKey: "nav.sectionConfig",
    items: [
      { href: "/dashboard/people", labelKey: "nav.people", icon: Users },
      { href: "/dashboard/companies", labelKey: "nav.companies", icon: Building2 },
      { href: "/dashboard/templates", labelKey: "nav.templates", icon: FileCode2 },
      { href: "/dashboard/sla", labelKey: "nav.sla", icon: Shield },
      { href: "/dashboard/notifications", labelKey: "nav.notifications", icon: BellRing },
    ],
  },
  {
    titleKey: "nav.sectionSystem",
    items: [
      { href: "/dashboard/reports", labelKey: "nav.reports", icon: FileText },
      { href: "/dashboard/audit-log", labelKey: "nav.auditLog", icon: ScrollText },
      { href: "/dashboard/settings", labelKey: "nav.settings", icon: Settings },
    ],
  },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useLocale();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close mobile sidebar on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Prevent body scroll when mobile sidebar is open
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  const sidebarContent = (
    <>
      {/* Nav */}
      <nav className="flex flex-col gap-y-1 flex-1 overflow-y-auto">
        {navSections.map((section) => (
          <div key={section.titleKey} className="mb-3">
            <p className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-widest text-muted/60">
              {t(section.titleKey)}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive =
                  item.href === "/dashboard"
                    ? pathname === "/dashboard"
                    : pathname.startsWith(item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
                      isActive
                        ? "text-primary-container bg-white/60 shadow-sm"
                        : "text-muted hover:text-slate-900 hover:bg-slate-200/40"
                    }`}
                  >
                    <Icon className="h-[18px] w-[18px]" />
                    <span>{t(item.labelKey)}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="pt-4 border-t border-slate-200/50 space-y-2">
        <LanguageSwitcher />
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted hover:text-red-600 hover:bg-red-50/60 transition-colors"
        >
          <LogOut className="h-[18px] w-[18px]" />
          {t("nav.signOut")}
        </button>
      </div>
    </>
  );

  return (
    <div className="flex h-full">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-64 h-screen fixed left-0 top-0 overflow-y-auto bg-slate-50/70 backdrop-blur-xl flex-col p-6 gap-y-2 text-sm tracking-tight z-50 border-r border-slate-200/30">
        <div className="mb-8 px-2">
          <h1 className="text-lg font-semibold tracking-tight text-slate-900">
            MailPulse
          </h1>
          <p className="text-[11px] text-muted">Management Suite</p>
        </div>
        {sidebarContent}
      </aside>

      {/* Mobile Sidebar Overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 sidebar-overlay lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-full w-72 bg-white/95 backdrop-blur-xl flex flex-col p-6 gap-y-2 text-sm tracking-tight z-50 shadow-2xl transition-transform duration-300 lg:hidden ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-slate-900">
              MailPulse
            </h1>
            <p className="text-[11px] text-muted">Management Suite</p>
          </div>
          <button
            onClick={() => setMobileOpen(false)}
            className="p-1.5 rounded-lg text-muted hover:bg-slate-100"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        {sidebarContent}
      </aside>

      {/* Main Area */}
      <div className="flex-1 flex flex-col lg:ml-64 min-h-screen">
        {/* Header */}
        <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-md flex items-center h-16 px-4 md:px-8 border-b border-slate-200/30 shadow-sm gap-4">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-2 rounded-lg text-muted hover:bg-slate-100 lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>

          <h2 className="text-sm font-bold tracking-tight text-on-surface lg:hidden">
            MailPulse
          </h2>

          <div className="relative flex-1 max-w-md hidden sm:block">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
            <input
              className="w-full bg-surface-low border-none rounded-xl py-2 pl-10 pr-4 text-sm focus:ring-2 focus:ring-primary-container/20 transition-all outline-none placeholder:text-slate-400"
              placeholder={t("common.search") + "..."}
              type="text"
            />
          </div>

          <div className="flex-1 lg:hidden" />

          <div className="flex items-center gap-2">
            <button className="p-2 text-muted hover:text-slate-900 transition-colors relative rounded-lg hover:bg-slate-100">
              <Bell className="h-5 w-5" />
              <span className="absolute top-2 right-2 w-2 h-2 bg-primary-container rounded-full ring-2 ring-white" />
            </button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto">
          <div className="p-4 md:p-8 lg:p-10">{children}</div>
        </main>
      </div>
    </div>
  );
}
