"use client";

import { useEffect, useState, useCallback } from "react";
import { Download } from "lucide-react";
import { useLocale } from "@/lib/i18n";
import type { DigestRun } from "@/lib/types";

type DigestRunWithCompany = DigestRun & {
  company: { id: string; name: string } | null;
};

export default function ReportsPage() {
  const { t } = useLocale();
  const [reports, setReports] = useState<DigestRunWithCompany[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchReports = useCallback(async () => {
    setLoading(true);
    const res = await fetch("/api/reports");
    const data = await res.json();
    setReports(Array.isArray(data) ? data : []);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">
        {t("reports.title")}
      </h1>

      {loading ? (
        <div className="text-center py-12 text-slate-400">{t("common.loading")}</div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left">
                <th className="px-5 py-3 font-medium text-slate-500">{t("reports.date")}</th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("reports.company")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("reports.totalEmails")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("reports.newEmails")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("reports.highPriority")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("reports.actionItems")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("reports.status")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("reports.telegram")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("reports.download")}
                </th>
              </tr>
            </thead>
            <tbody>
              {reports.length === 0 ? (
                <tr>
                  <td
                    colSpan={9}
                    className="px-5 py-8 text-center text-slate-400"
                  >
                    {t("reports.noData")}
                  </td>
                </tr>
              ) : (
                reports.map((run) => (
                  <tr
                    key={run.id}
                    className="border-b border-slate-50 hover:bg-slate-50"
                  >
                    <td className="px-5 py-3 text-slate-700">
                      {new Date(run.started_at).toLocaleDateString()}
                    </td>
                    <td className="px-5 py-3 font-medium text-slate-900">
                      {run.company?.name ?? "—"}
                    </td>
                    <td className="px-5 py-3 text-slate-700">
                      {run.total_emails}
                    </td>
                    <td className="px-5 py-3 text-slate-700">
                      {run.new_emails}
                    </td>
                    <td className="px-5 py-3">
                      {run.high_priority > 0 ? (
                        <span className="inline-flex rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">
                          {run.high_priority}
                        </span>
                      ) : (
                        <span className="text-slate-400">0</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-slate-700">
                      {run.action_items_created}
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      <div className="flex items-center gap-1.5">
                        {run.lark_delivered ? (
                          <span className="inline-flex items-center gap-1 text-emerald-600">
                            <span className="h-2 w-2 rounded-full bg-emerald-500" />
                            {t("common.yes")}
                          </span>
                        ) : run.telegram_delivered ? (
                          <span className="inline-flex items-center gap-1 text-emerald-600">
                            <span className="h-2 w-2 rounded-full bg-emerald-500" />
                            {t("common.yes")}
                          </span>
                        ) : (
                          <span className="text-slate-400">{t("common.no")}</span>
                        )}
                        {run.telegram_delivered && !run.lark_delivered && (
                          <span className="text-xs text-slate-400">(TG)</span>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-1">
                        {run.report_docx_url && (
                          <a
                            href={run.report_docx_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100"
                          >
                            <Download className="h-3 w-3" />
                            DOCX
                          </a>
                        )}
                        {run.report_pdf_url && (
                          <a
                            href={run.report_pdf_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 rounded-md bg-violet-50 px-2 py-1 text-xs font-medium text-violet-700 hover:bg-violet-100"
                          >
                            <Download className="h-3 w-3" />
                            PDF
                          </a>
                        )}
                        {!run.report_docx_url && !run.report_pdf_url && (
                          <span className="text-slate-400 text-xs">—</span>
                        )}
                      </div>
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
