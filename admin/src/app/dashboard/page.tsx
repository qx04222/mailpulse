"use client";

import { useEffect, useState, useCallback } from "react";
import { useLocale } from "@/lib/i18n";
import {
  Building2,
  Users,
  Mail,
  CheckSquare,
} from "lucide-react";

interface DashboardData {
  totalCompanies: number;
  totalPeople: number;
  totalEmails: number;
  totalActionItems: number;
  recentRuns: Record<string, unknown>[];
}

export default function DashboardPage() {
  const { t } = useLocale();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const res = await fetch("/api/dashboard");
    const json = await res.json();
    setData(json);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading || !data) {
    return (
      <div className="text-center py-12 text-slate-400">
        {t("common.loading")}
      </div>
    );
  }

  const stats = [
    {
      label: t("dashboard.totalCompanies"),
      value: data.totalCompanies,
      icon: Building2,
      color: "bg-blue-500",
    },
    {
      label: t("dashboard.totalPeople"),
      value: data.totalPeople,
      icon: Users,
      color: "bg-emerald-500",
    },
    {
      label: t("dashboard.totalThreads"),
      value: data.totalEmails,
      icon: Mail,
      color: "bg-violet-500",
    },
    {
      label: t("dashboard.totalActions"),
      value: data.totalActionItems,
      icon: CheckSquare,
      color: "bg-amber-500",
    },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">{t("nav.dashboard")}</h1>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl border border-slate-200 bg-white p-5"
          >
            <div className="flex items-center gap-3">
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-lg ${stat.color}`}
              >
                <stat.icon className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="text-sm text-slate-500">{stat.label}</p>
                <p className="text-2xl font-bold text-slate-900">
                  {stat.value}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Recent Digest Runs */}
      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="text-lg font-semibold text-slate-900">
            {t("dashboard.recentRuns")}
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left">
                <th className="px-5 py-3 font-medium text-slate-500">{t("dashboard.date")}</th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("dashboard.company")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("dashboard.emails")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("common.status")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("dashboard.telegram")}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.recentRuns.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-5 py-8 text-center text-slate-400"
                  >
                    {t("dashboard.noRuns")}
                  </td>
                </tr>
              ) : (
                data.recentRuns.map(
                  (run: Record<string, unknown>) => (
                    <tr
                      key={run.id as string}
                      className="border-b border-slate-50 hover:bg-slate-50"
                    >
                      <td className="px-5 py-3 text-slate-700">
                        {new Date(run.started_at as string).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3 text-slate-700">
                        {(run.company as Record<string, unknown>)?.name as string ?? "—"}
                      </td>
                      <td className="px-5 py-3 text-slate-700">
                        {run.total_emails as number}
                      </td>
                      <td className="px-5 py-3">
                        <StatusBadge status={run.status as string} />
                      </td>
                      <td className="px-5 py-3 text-slate-700">
                        <div className="flex items-center gap-1.5">
                          {(run.lark_delivered as boolean) ? (
                            <span className="inline-flex items-center gap-1 text-emerald-600">
                              <span className="h-2 w-2 rounded-full bg-emerald-500" />
                              {t("dashboard.delivered")}
                            </span>
                          ) : (run.telegram_delivered as boolean) ? (
                            <span className="inline-flex items-center gap-1 text-emerald-600">
                              <span className="h-2 w-2 rounded-full bg-emerald-500" />
                              {t("dashboard.delivered")}
                            </span>
                          ) : (
                            "—"
                          )}
                          {(run.telegram_delivered as boolean) && !(run.lark_delivered as boolean) && (
                            <span className="text-xs text-slate-400">(TG)</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                )
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: "bg-emerald-50 text-emerald-700",
    running: "bg-blue-50 text-blue-700",
    failed: "bg-red-50 text-red-700",
  };
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[status] ?? "bg-slate-100 text-slate-600"}`}
    >
      {status}
    </span>
  );
}
