import { createAdminClient } from "@/lib/supabase";
import {
  Building2,
  Users,
  Mail,
  CheckSquare,
} from "lucide-react";

async function getDashboardData() {
  const supabase = createAdminClient();

  const [companies, people, threads, actionItems, digestRuns] =
    await Promise.all([
      supabase.from("companies").select("id", { count: "exact", head: true }),
      supabase.from("people").select("id", { count: "exact", head: true }),
      supabase.from("threads").select("id", { count: "exact", head: true }),
      supabase.from("action_items").select("id", { count: "exact", head: true }),
      supabase
        .from("digest_runs")
        .select("*, companies(name)")
        .order("started_at", { ascending: false })
        .limit(10),
    ]);

  return {
    totalCompanies: companies.count ?? 0,
    totalPeople: people.count ?? 0,
    totalEmails: threads.count ?? 0,
    totalActionItems: actionItems.count ?? 0,
    recentRuns: (digestRuns.data ?? []).map((r: Record<string, unknown>) => ({
      ...r,
      company: r.companies,
    })),
  };
}

export default async function DashboardPage() {
  const data = await getDashboardData();

  const stats = [
    {
      label: "Companies",
      value: data.totalCompanies,
      icon: Building2,
      color: "bg-blue-500",
    },
    {
      label: "People",
      value: data.totalPeople,
      icon: Users,
      color: "bg-emerald-500",
    },
    {
      label: "Email Threads",
      value: data.totalEmails,
      icon: Mail,
      color: "bg-violet-500",
    },
    {
      label: "Action Items",
      value: data.totalActionItems,
      icon: CheckSquare,
      color: "bg-amber-500",
    },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Dashboard</h1>

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
            Recent Digest Runs
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left">
                <th className="px-5 py-3 font-medium text-slate-500">Date</th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  Company
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  Emails
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  Status
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  Telegram
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
                    No digest runs yet
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
                        {run.telegram_delivered ? "Delivered" : "—"}
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
