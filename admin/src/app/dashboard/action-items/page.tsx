"use client";

import { useEffect, useState, useCallback } from "react";
import { useLocale } from "@/lib/i18n";
import type { ActionItem, Company, Person } from "@/lib/types";

type ActionItemExpanded = ActionItem & {
  company: { id: string; name: string } | null;
  assigned_to: { id: string; name: string } | null;
};

export default function ActionItemsPage() {
  const { t } = useLocale();
  const [items, setItems] = useState<ActionItemExpanded[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState("");
  const [filterCompany, setFilterCompany] = useState("");
  const [filterAssignee, setFilterAssignee] = useState("");

  const fetchItems = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filterStatus) params.set("status", filterStatus);
    if (filterCompany) params.set("company_id", filterCompany);
    if (filterAssignee) params.set("assigned_to", filterAssignee);
    const qs = params.toString() ? `?${params.toString()}` : "";
    const res = await fetch(`/api/action-items${qs}`);
    const data = await res.json();
    setItems(Array.isArray(data) ? data : []);
    setLoading(false);
  }, [filterStatus, filterCompany, filterAssignee]);

  const fetchFilters = useCallback(async () => {
    const [companiesRes, peopleRes] = await Promise.all([
      fetch("/api/companies"),
      fetch("/api/people"),
    ]);
    const companiesData = await companiesRes.json();
    const peopleData = await peopleRes.json();
    setCompanies(Array.isArray(companiesData) ? companiesData : []);
    setPeople(Array.isArray(peopleData) ? peopleData : []);
  }, []);

  useEffect(() => {
    fetchFilters();
  }, [fetchFilters]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  async function updateStatus(id: string, newStatus: string) {
    await fetch("/api/action-items", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, status: newStatus }),
    });
    fetchItems();
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">{t("actionItems.title")}</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        >
          <option value="">{t("actionItems.allStatuses")}</option>
          <option value="pending">Pending</option>
          <option value="in_progress">In Progress</option>
          <option value="overdue">Overdue</option>
          <option value="resolved">Resolved</option>
          <option value="dismissed">Dismissed</option>
        </select>

        <select
          value={filterCompany}
          onChange={(e) => setFilterCompany(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        >
          <option value="">{t("actionItems.allCompanies")}</option>
          {companies.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>

        <select
          value={filterAssignee}
          onChange={(e) => setFilterAssignee(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        >
          <option value="">{t("actionItems.allAssignees")}</option>
          {people.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">{t("common.loading")}</div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left">
                <th className="px-5 py-3 font-medium text-slate-500">{t("actionItems.title")}</th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("actionItems.priority")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("common.status")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("actionItems.assignee")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("reports.company")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("actionItems.dueDate")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("common.actions")}
                </th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-5 py-8 text-center text-slate-400"
                  >
                    {t("actionItems.noData")}
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr
                    key={item.id}
                    className="border-b border-slate-50 hover:bg-slate-50"
                  >
                    <td className="px-5 py-3">
                      <p className="font-medium text-slate-900">
                        {item.title}
                      </p>
                      {item.description && (
                        <p className="text-xs text-slate-500 mt-0.5 truncate max-w-xs">
                          {item.description}
                        </p>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <PriorityBadge priority={item.priority} />
                    </td>
                    <td className="px-5 py-3">
                      <ActionStatusBadge status={item.status} />
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {item.assigned_to?.name ?? t("actionItems.unassigned")}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {item.company?.name ?? "—"}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {item.due_date
                        ? new Date(item.due_date).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="px-5 py-3">
                      {item.status !== "resolved" &&
                        item.status !== "dismissed" && (
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => updateStatus(item.id, "resolved")}
                              className="rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
                            >
                              {t("actionItems.resolve")}
                            </button>
                            <button
                              onClick={() => updateStatus(item.id, "dismissed")}
                              className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-200"
                            >
                              {t("actionItems.dismiss")}
                            </button>
                          </div>
                        )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const styles: Record<string, string> = {
    high: "bg-red-50 text-red-700",
    medium: "bg-amber-50 text-amber-700",
    low: "bg-slate-100 text-slate-600",
  };
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[priority] ?? "bg-slate-100 text-slate-600"}`}
    >
      {priority}
    </span>
  );
}

function ActionStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "bg-amber-50 text-amber-700",
    in_progress: "bg-blue-50 text-blue-700",
    overdue: "bg-red-50 text-red-700",
    resolved: "bg-emerald-50 text-emerald-700",
    dismissed: "bg-slate-100 text-slate-500",
  };
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[status] ?? "bg-slate-100 text-slate-600"}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}
