"use client";

import { useEffect, useState, useCallback } from "react";
import { Plus, Pencil, Trash2, X } from "lucide-react";
import { useLocale } from "@/lib/i18n";
import type { Person } from "@/lib/types";

interface NotificationRule {
  id: string;
  person_id: string;
  channel: "email" | "telegram" | "both" | "lark" | "email_lark" | "web";
  event_types: string[];
  min_severity: "info" | "warning" | "critical";
  only_assigned: boolean;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  is_active: boolean;
  created_at: string;
}

const EVENT_TYPES = [
  "new_client",
  "new_inquiry",
  "quote_sent",
  "overdue_warning",
  "complaint",
  "deal_closed",
  "sla_breach",
];

const CHANNELS = ["email", "lark", "email_lark", "telegram", "both", "web"] as const;
const SEVERITIES = ["info", "warning", "critical"] as const;

export default function NotificationsPage() {
  const { t } = useLocale();
  const [rules, setRules] = useState<NotificationRule[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<NotificationRule | null>(null);

  const fetchRules = useCallback(async () => {
    setLoading(true);
    const [rulesRes, peopleRes] = await Promise.all([
      fetch("/api/notifications"),
      fetch("/api/people"),
    ]);
    const rulesData = await rulesRes.json();
    const peopleData = await peopleRes.json();
    setRules(Array.isArray(rulesData) ? rulesData : []);
    setPeople(Array.isArray(peopleData) ? peopleData : []);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const personName = (id: string) =>
    people.find((p) => p.id === id)?.name ?? id;

  async function handleDelete(id: string) {
    if (!confirm(t("notifications.confirmDelete"))) return;
    await fetch(`/api/notifications?id=${id}`, { method: "DELETE" });
    fetchRules();
  }

  async function toggleActive(rule: NotificationRule) {
    await fetch("/api/notifications", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: rule.id, is_active: !rule.is_active }),
    });
    fetchRules();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          {t("notifications.title")}
        </h1>
        <button
          onClick={() => {
            setEditing(null);
            setShowForm(true);
          }}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          {t("notifications.addRule")}
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">
          {t("common.loading")}
        </div>
      ) : rules.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white px-5 py-12 text-center text-slate-400">
          {t("notifications.noData")}
        </div>
      ) : (
        <div className="space-y-3">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className={`rounded-xl border bg-white p-5 ${
                rule.is_active ? "border-slate-200" : "border-slate-200 opacity-60"
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                      {personName(rule.person_id)}
                    </span>
                    <span className="inline-flex rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                      {t(`notifications.channels.${rule.channel}`)}
                    </span>
                    <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                      {t(`events.severity.${rule.min_severity}`)}+
                    </span>
                    {rule.only_assigned && (
                      <span className="inline-flex rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
                        {t("notifications.onlyAssigned")}
                      </span>
                    )}
                    {!rule.is_active && (
                      <span className="inline-flex rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-600">
                        {t("common.inactive")}
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-1">
                    {rule.event_types.map((et) => (
                      <span
                        key={et}
                        className="inline-flex rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600"
                      >
                        {t(`events.types.${et}`) !== `events.types.${et}`
                          ? t(`events.types.${et}`)
                          : et}
                      </span>
                    ))}
                    {rule.event_types.length === 0 && (
                      <span className="text-xs text-slate-400">
                        {t("common.all")}
                      </span>
                    )}
                  </div>

                  {(rule.quiet_hours_start || rule.quiet_hours_end) && (
                    <p className="text-xs text-slate-500">
                      {t("notifications.quietHours")}: {rule.quiet_hours_start ?? "—"}{" "}
                      - {rule.quiet_hours_end ?? "—"}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => toggleActive(rule)}
                    className={`rounded-md px-2 py-1 text-xs font-medium ${
                      rule.is_active
                        ? "bg-slate-100 text-slate-600 hover:bg-slate-200"
                        : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                    }`}
                  >
                    {rule.is_active ? t("common.inactive") : t("common.active")}
                  </button>
                  <button
                    onClick={() => {
                      setEditing(rule);
                      setShowForm(true);
                    }}
                    className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-blue-600"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(rule.id)}
                    className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-red-600"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <NotificationForm
          rule={editing}
          people={people}
          t={t}
          onClose={() => {
            setShowForm(false);
            setEditing(null);
          }}
          onSave={() => {
            setShowForm(false);
            setEditing(null);
            fetchRules();
          }}
        />
      )}
    </div>
  );
}

function NotificationForm({
  rule,
  people,
  t,
  onClose,
  onSave,
}: {
  rule: NotificationRule | null;
  people: Person[];
  t: (key: string) => string;
  onClose: () => void;
  onSave: () => void;
}) {
  const [personId, setPersonId] = useState(rule?.person_id ?? "");
  const [channel, setChannel] = useState<NotificationRule["channel"]>(
    rule?.channel ?? "email"
  );
  const [eventTypes, setEventTypes] = useState<string[]>(
    rule?.event_types ?? []
  );
  const [minSeverity, setMinSeverity] = useState<NotificationRule["min_severity"]>(
    rule?.min_severity ?? "info"
  );
  const [onlyAssigned, setOnlyAssigned] = useState(
    rule?.only_assigned ?? false
  );
  const [quietStart, setQuietStart] = useState(
    rule?.quiet_hours_start ?? ""
  );
  const [quietEnd, setQuietEnd] = useState(rule?.quiet_hours_end ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function toggleEventType(et: string) {
    setEventTypes((prev) =>
      prev.includes(et) ? prev.filter((x) => x !== et) : [...prev, et]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    if (!personId) {
      setError(t("notifications.personRequired"));
      setSaving(false);
      return;
    }

    const payload = {
      id: rule?.id,
      person_id: personId,
      channel,
      event_types: eventTypes,
      min_severity: minSeverity,
      only_assigned: onlyAssigned,
      quiet_hours_start: quietStart || null,
      quiet_hours_end: quietEnd || null,
      is_active: rule?.is_active ?? true,
    };

    const res = await fetch("/api/notifications", {
      method: rule ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const data = await res.json();
      setError(data.error || "Failed to save");
      setSaving(false);
      return;
    }

    onSave();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900">
            {rule ? t("notifications.editRule") : t("notifications.addRule")}
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:text-slate-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("notifications.person")}
            </label>
            <select
              value={personId}
              onChange={(e) => setPersonId(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              required
              disabled={!!rule}
            >
              <option value="">--</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("notifications.channel")}
            </label>
            <select
              value={channel}
              onChange={(e) =>
                setChannel(e.target.value as NotificationRule["channel"])
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              {CHANNELS.map((ch) => (
                <option key={ch} value={ch}>
                  {t(`notifications.channels.${ch}`)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              {t("notifications.eventTypes")}
            </label>
            <div className="space-y-1.5 max-h-40 overflow-y-auto">
              {EVENT_TYPES.map((et) => (
                <label
                  key={et}
                  className="flex items-center gap-2 text-sm text-slate-600"
                >
                  <input
                    type="checkbox"
                    checked={eventTypes.includes(et)}
                    onChange={() => toggleEventType(et)}
                    className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  {t(`events.types.${et}`) !== `events.types.${et}`
                    ? t(`events.types.${et}`)
                    : et}
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("notifications.minSeverity")}
            </label>
            <select
              value={minSeverity}
              onChange={(e) =>
                setMinSeverity(
                  e.target.value as NotificationRule["min_severity"]
                )
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>
                  {t(`events.severity.${s}`)}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="only_assigned"
              checked={onlyAssigned}
              onChange={(e) => setOnlyAssigned(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="only_assigned" className="text-sm text-slate-700">
              {t("notifications.onlyAssigned")}
            </label>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                {t("notifications.quietStart")}
              </label>
              <input
                type="time"
                value={quietStart}
                onChange={(e) => setQuietStart(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                {t("notifications.quietEnd")}
              </label>
              <input
                type="time"
                value={quietEnd}
                onChange={(e) => setQuietEnd(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              />
            </div>
          </div>

          {error && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? t("common.saving") : t("common.save")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
