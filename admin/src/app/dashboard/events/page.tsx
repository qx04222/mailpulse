"use client";

import { useEffect, useState, useCallback } from "react";
import { useLocale } from "@/lib/i18n";
import type { Company } from "@/lib/types";

interface EventItem {
  id: string;
  event_type: string;
  severity: "info" | "warning" | "critical";
  title: string;
  description: string | null;
  is_read: boolean;
  is_resolved: boolean;
  company_id: string | null;
  client_id: string | null;
  person_id: string | null;
  created_at: string;
  company?: { id: string; name: string } | null;
  client?: { id: string; name: string; email: string } | null;
  person?: { id: string; name: string } | null;
}

type FilterTab = "all" | "unread" | "critical";

function timeAgo(dateStr: string, t: (key: string) => string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMs / 3600000);
  const diffDay = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return t("events.ago.justNow");
  if (diffMin < 60) return `${diffMin} ${t("events.ago.minutesAgo")}`;
  if (diffHr < 24) return `${diffHr} ${t("events.ago.hoursAgo")}`;
  return `${diffDay} ${t("events.ago.daysAgo")}`;
}

export default function EventsPage() {
  const { t } = useLocale();
  const [events, setEvents] = useState<EventItem[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<FilterTab>("all");
  const [filterCompany, setFilterCompany] = useState("");

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filterCompany) params.set("company_id", filterCompany);
    if (tab === "unread") params.set("is_read", "false");
    if (tab === "critical") params.set("severity", "critical");
    const qs = params.toString() ? `?${params.toString()}` : "";
    const res = await fetch(`/api/events${qs}`);
    const data = await res.json();
    setEvents(Array.isArray(data) ? data : []);
    setLoading(false);
  }, [filterCompany, tab]);

  const fetchCompanies = useCallback(async () => {
    const res = await fetch("/api/companies");
    const data = await res.json();
    setCompanies(Array.isArray(data) ? data : []);
  }, []);

  useEffect(() => {
    fetchCompanies();
  }, [fetchCompanies]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  async function markRead(id: string) {
    await fetch("/api/events", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, is_read: true }),
    });
    fetchEvents();
  }

  async function markResolved(id: string) {
    await fetch("/api/events", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, is_resolved: true, is_read: true }),
    });
    fetchEvents();
  }

  const severityDot: Record<string, string> = {
    info: "bg-blue-500",
    warning: "bg-amber-500",
    critical: "bg-red-500",
  };

  const severityBadge: Record<string, string> = {
    info: "bg-blue-50 text-blue-700",
    warning: "bg-amber-50 text-amber-700",
    critical: "bg-red-50 text-red-700",
  };

  const typeBadgeStyle = "bg-slate-100 text-slate-600";

  const tabs: { key: FilterTab; labelKey: string }[] = [
    { key: "all", labelKey: "events.allEvents" },
    { key: "unread", labelKey: "events.unread" },
    { key: "critical", labelKey: "events.critical" },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">
        {t("events.title")}
      </h1>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex rounded-lg border border-slate-200 bg-white overflow-hidden">
          {tabs.map((tb) => (
            <button
              key={tb.key}
              onClick={() => setTab(tb.key)}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                tab === tb.key
                  ? "bg-blue-600 text-white"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              {t(tb.labelKey)}
            </button>
          ))}
        </div>

        <select
          value={filterCompany}
          onChange={(e) => setFilterCompany(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        >
          <option value="">{t("events.allCompanies")}</option>
          {companies.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      {/* Event Timeline */}
      {loading ? (
        <div className="text-center py-12 text-slate-400">
          {t("common.loading")}
        </div>
      ) : events.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white px-5 py-12 text-center text-slate-400">
          {t("events.noData")}
        </div>
      ) : (
        <div className="space-y-2">
          {events.map((event) => (
            <div
              key={event.id}
              className={`rounded-xl border bg-white p-4 transition-colors ${
                event.is_read
                  ? "border-slate-200"
                  : "border-blue-200 bg-blue-50/30"
              }`}
            >
              <div className="flex items-start gap-3">
                {/* Severity dot */}
                <div className="mt-1.5">
                  <div
                    className={`h-2.5 w-2.5 rounded-full ${
                      severityDot[event.severity] ?? "bg-slate-400"
                    }`}
                  />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                        severityBadge[event.severity] ?? "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {t(`events.severity.${event.severity}`)}
                    </span>
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${typeBadgeStyle}`}
                    >
                      {t(`events.types.${event.event_type}`) !== `events.types.${event.event_type}`
                        ? t(`events.types.${event.event_type}`)
                        : event.event_type}
                    </span>
                    {event.company && (
                      <span className="text-xs text-slate-500">
                        {event.company.name}
                      </span>
                    )}
                  </div>

                  <p className="text-sm font-medium text-slate-900">
                    {event.title}
                  </p>
                  {event.description && (
                    <p className="text-sm text-slate-600 mt-0.5">
                      {event.description}
                    </p>
                  )}

                  {/* Related entities */}
                  <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-500">
                    {event.client && (
                      <span>
                        {event.client.name ?? event.client.email}
                      </span>
                    )}
                    {event.person && <span>{event.person.name}</span>}
                    <span>{timeAgo(event.created_at, t)}</span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1 shrink-0">
                  {!event.is_read && (
                    <button
                      onClick={() => markRead(event.id)}
                      className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-200"
                    >
                      {t("events.markRead")}
                    </button>
                  )}
                  {!event.is_resolved && (
                    <button
                      onClick={() => markResolved(event.id)}
                      className="rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
                    >
                      {t("events.markResolved")}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
