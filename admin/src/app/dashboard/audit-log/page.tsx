"use client";

import { useEffect, useState, useCallback } from "react";
import { useLocale } from "@/lib/i18n";

interface AuditEntry {
  id: string;
  actor: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  description: string | null;
  changes: Record<string, unknown> | null;
  created_at: string;
}

const ACTION_STYLES: Record<string, string> = {
  create: "bg-emerald-50 text-emerald-700",
  update: "bg-blue-50 text-blue-700",
  delete: "bg-red-50 text-red-700",
  login: "bg-violet-50 text-violet-700",
  resolve: "bg-amber-50 text-amber-700",
  dismiss: "bg-slate-100 text-slate-600",
};

export default function AuditLogPage() {
  const { t } = useLocale();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filterAction, setFilterAction] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const fetchEntries = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filterAction) params.set("action", filterAction);
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    const qs = params.toString() ? `?${params.toString()}` : "";
    const res = await fetch(`/api/audit-log${qs}`);
    const result = await res.json();
    setEntries(result.data ?? []);
    setTotal(result.total ?? 0);
    setLoading(false);
  }, [filterAction, offset]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  useEffect(() => {
    setOffset(0);
  }, [filterAction]);

  const actionTypes = ["create", "update", "delete", "login", "resolve", "dismiss"];

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">
        {t("audit.title")}
      </h1>

      {/* Filter */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={filterAction}
          onChange={(e) => setFilterAction(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        >
          <option value="">{t("audit.allActions")}</option>
          {actionTypes.map((a) => (
            <option key={a} value={a}>
              {t(`audit.actions.${a}`) !== `audit.actions.${a}`
                ? t(`audit.actions.${a}`)
                : a}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">
          {t("common.loading")}
        </div>
      ) : (
        <>
          <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left">
                  <th className="px-5 py-3 font-medium text-slate-500">
                    {t("audit.time")}
                  </th>
                  <th className="px-5 py-3 font-medium text-slate-500">
                    {t("audit.actor")}
                  </th>
                  <th className="px-5 py-3 font-medium text-slate-500">
                    {t("audit.action")}
                  </th>
                  <th className="px-5 py-3 font-medium text-slate-500">
                    {t("audit.entity")}
                  </th>
                  <th className="px-5 py-3 font-medium text-slate-500">
                    {t("audit.description")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {entries.length === 0 ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-5 py-8 text-center text-slate-400"
                    >
                      {t("audit.noData")}
                    </td>
                  </tr>
                ) : (
                  entries.map((entry) => (
                    <tr
                      key={entry.id}
                      className="border-b border-slate-50 hover:bg-slate-50"
                    >
                      <td className="px-5 py-3 text-slate-600 whitespace-nowrap">
                        {new Date(entry.created_at).toLocaleString()}
                      </td>
                      <td className="px-5 py-3 text-slate-700">
                        {entry.actor ?? "—"}
                      </td>
                      <td className="px-5 py-3">
                        <span
                          className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${
                            ACTION_STYLES[entry.action] ??
                            "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {t(`audit.actions.${entry.action}`) !==
                          `audit.actions.${entry.action}`
                            ? t(`audit.actions.${entry.action}`)
                            : entry.action}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-slate-600">
                        {entry.entity_type ?? "—"}
                      </td>
                      <td className="px-5 py-3 text-slate-600 max-w-xs truncate">
                        {entry.description ?? "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {total > limit && (
            <div className="flex items-center justify-between mt-4">
              <p className="text-sm text-slate-500">
                {offset + 1}-{Math.min(offset + limit, total)} / {total}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  disabled={offset === 0}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  {t("common.back")}
                </button>
                <button
                  onClick={() => setOffset(offset + limit)}
                  disabled={offset + limit >= total}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
