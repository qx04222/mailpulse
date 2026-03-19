"use client";

import { useEffect, useState, useCallback } from "react";
import { useLocale } from "@/lib/i18n";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#ec4899",
  "#06b6d4",
  "#84cc16",
];

export default function AnalyticsPage() {
  const { t } = useLocale();
  const [volumeData, setVolumeData] = useState<{
    data: Record<string, unknown>[];
    companies: string[];
  }>({ data: [], companies: [] });
  const [responseData, setResponseData] = useState<
    { week: string; avgHours: number }[]
  >([]);
  const [workloadData, setWorkloadData] = useState<
    { name: string; value: number }[]
  >([]);
  const [funnelData, setFunnelData] = useState<
    { status: string; count: number }[]
  >([]);
  const [comparisonData, setComparisonData] = useState<
    Record<string, unknown>[]
  >([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    const [vol, resp, work, fun, comp] = await Promise.all([
      fetch("/api/analytics?type=volume").then((r) => r.json()),
      fetch("/api/analytics?type=response_time").then((r) => r.json()),
      fetch("/api/analytics?type=workload").then((r) => r.json()),
      fetch("/api/analytics?type=funnel").then((r) => r.json()),
      fetch("/api/analytics?type=comparison").then((r) => r.json()),
    ]);
    setVolumeData(vol);
    setResponseData(resp.data ?? []);
    setWorkloadData(work.data ?? []);
    setFunnelData(fun.data ?? []);
    setComparisonData(comp.data ?? []);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  if (loading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-slate-900 mb-6">
          {t("analytics.title")}
        </h1>
        <div className="text-center py-12 text-slate-400">
          {t("common.loading")}
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">
        {t("analytics.title")}
      </h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Email Volume */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-base font-semibold text-slate-900 mb-4">
            {t("analytics.emailVolume")}
          </h2>
          {volumeData.data.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-slate-400 text-sm">
              {t("analytics.noData")}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={volumeData.data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                {volumeData.companies.map((name, i) => (
                  <Bar
                    key={name}
                    dataKey={name}
                    fill={COLORS[i % COLORS.length]}
                    radius={[4, 4, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Response Time */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-base font-semibold text-slate-900 mb-4">
            {t("analytics.responseTime")}
          </h2>
          {responseData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-slate-400 text-sm">
              {t("analytics.noData")}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={responseData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="avgHours"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  name={t("analytics.avgResponseHours")}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Workload Distribution */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-base font-semibold text-slate-900 mb-4">
            {t("analytics.workload")}
          </h2>
          {workloadData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-slate-400 text-sm">
              {t("analytics.noData")}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={workloadData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {workloadData.map((_, i) => (
                    <Cell
                      key={`cell-${i}`}
                      fill={COLORS[i % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Client Funnel */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-base font-semibold text-slate-900 mb-4">
            {t("analytics.clientFunnel")}
          </h2>
          {funnelData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-slate-400 text-sm">
              {t("analytics.noData")}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={funnelData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis
                  dataKey="status"
                  type="category"
                  tick={{ fontSize: 12 }}
                  width={90}
                />
                <Tooltip />
                <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Company Comparison Table */}
      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="text-base font-semibold text-slate-900">
            {t("analytics.companyComparison")}
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left">
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("companies.name")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("dashboard.totalThreads")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("dashboard.totalActions")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("dashboard.recentRuns")}
                </th>
              </tr>
            </thead>
            <tbody>
              {comparisonData.length === 0 ? (
                <tr>
                  <td
                    colSpan={4}
                    className="px-5 py-8 text-center text-slate-400"
                  >
                    {t("analytics.noData")}
                  </td>
                </tr>
              ) : (
                comparisonData.map((row) => (
                  <tr
                    key={row.name as string}
                    className="border-b border-slate-50 hover:bg-slate-50"
                  >
                    <td className="px-5 py-3 font-medium text-slate-900">
                      {row.name as string}
                    </td>
                    <td className="px-5 py-3 text-slate-700">
                      {row.threads as number}
                    </td>
                    <td className="px-5 py-3 text-slate-700">
                      {row.actionItems as number}
                    </td>
                    <td className="px-5 py-3 text-slate-700">
                      {row.digestRuns as number}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
