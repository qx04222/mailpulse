"use client";

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
  Mail,
  Bell,
  BarChart3,
  FileCode2,
  BellRing,
  ScrollText,
  Shield,
  CalendarClock,
  Settings,
  MessageSquare,
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
      { href: "/dashboard/schedules", labelKey: "nav.schedules", icon: CalendarClock },
      { href: "/dashboard/notifications", labelKey: "nav.notifications", icon: BellRing },
      { href: "/dashboard/lark", labelKey: "nav.lark", icon: MessageSquare },
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

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="flex w-60 flex-col bg-slate-900 text-slate-300">
        <div className="flex h-14 items-center gap-2.5 border-b border-slate-800 px-5">
          <Mail className="h-5 w-5 text-blue-400" />
          <span className="text-sm font-semibold text-white">
            Email Digest
          </span>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-3">
          {navSections.map((section) => (
            <div key={section.titleKey} className="mb-3">
              <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {t(section.titleKey)}
              </p>
              <div className="space-y-0.5">
                {section.items.map((item) => {
                  const isActive =
                    item.href === "/dashboard"
                      ? pathname === "/dashboard"
                      : pathname.startsWith(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-blue-600/20 text-blue-400"
                          : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                      }`}
                    >
                      <item.icon className="h-4 w-4" />
                      {t(item.labelKey)}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-slate-800 p-3 space-y-1">
          <LanguageSwitcher />
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
          >
            <LogOut className="h-4 w-4" />
            {t("nav.signOut")}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto bg-slate-50">
        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}
