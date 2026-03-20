"use client";

import { useEffect, useState, useCallback } from "react";
import { Plus, Pencil, Trash2, X, Play } from "lucide-react";
import { useLocale } from "@/lib/i18n";
import type { Company, Person, DigestSchedule, DigestRun } from "@/lib/types";

const CRON_PRESETS: { labelKey: string; value: string }[] = [
  { labelKey: "schedules.cronPresets.daily", value: "0 8 * * *" },
  { labelKey: "schedules.cronPresets.weekdays", value: "0 8 * * 1-5" },
  { labelKey: "schedules.cronPresets.monThu", value: "0 8 * * 1,4" },
  { labelKey: "schedules.cronPresets.weekly", value: "0 8 * * 1" },
  { labelKey: "schedules.cronPresets.custom", value: "custom" },
];

const SECTION_OPTIONS = [
  "high_priority",
  "medium_priority",
  "followup",
  "client_details",
  "trash_review",
  "summary",
  "action_items",
] as const;

function cronToHuman(cron: string, t: (k: string) => string): string {
  for (const preset of CRON_PRESETS) {
    if (preset.value !== "custom" && preset.value === cron) {
      return t(preset.labelKey);
    }
  }
  return cron;
}

export default function SchedulesPage() {
  const { t } = useLocale();
  const [schedules, setSchedules] = useState<DigestSchedule[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [runs, setRuns] = useState<DigestRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<DigestSchedule | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const [schedulesRes, companiesRes, peopleRes, runsRes] = await Promise.all([
      fetch("/api/schedules"),
      fetch("/api/companies"),
      fetch("/api/people"),
      fetch("/api/reports"),
    ]);
    const schedulesData = await schedulesRes.json();
    const companiesData = await companiesRes.json();
    const peopleData = await peopleRes.json();
    const runsData = await runsRes.json();
    setSchedules(Array.isArray(schedulesData) ? schedulesData : []);
    setCompanies(Array.isArray(companiesData) ? companiesData : []);
    setPeople(Array.isArray(peopleData) ? peopleData : []);
    setRuns(Array.isArray(runsData) ? runsData.slice(0, 10) : []);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleDelete(id: string) {
    if (!confirm(t("schedules.confirmDelete"))) return;
    await fetch(`/api/schedules?id=${id}`, { method: "DELETE" });
    fetchData();
  }

  async function handleToggleActive(schedule: DigestSchedule) {
    await fetch("/api/schedules", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: schedule.id, is_active: !schedule.is_active }),
    });
    fetchData();
  }

  async function handleRunNow(id: string) {
    const res = await fetch(`/api/schedules/${id}/run`, { method: "POST" });
    if (res.ok) {
      alert(t("schedules.runTriggered"));
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          {t("schedules.title")}
        </h1>
        <button
          onClick={() => {
            setEditing(null);
            setShowForm(true);
          }}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          {t("schedules.addSchedule")}
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">
          {t("common.loading")}
        </div>
      ) : (
        <>
          {/* Schedules Table */}
          <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto mb-8">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left">
                  <th className="px-5 py-3 font-medium text-slate-500">
                    {t("schedules.name")}
                  </th>
                  <th className="px-5 py-3 font-medium text-slate-500">
                    {t("dashboard.company")}
                  </th>
                  <th className="px-5 py-3 font-medium text-slate-500">
                    {t("schedules.frequency")}
                  </th>
                  <th className="px-5 py-3 font-medium text-slate-500">
                    {t("schedules.targetType")}
                  </th>
                  <th className="px-5 py-3 font-medium text-slate-500">
                    {t("schedules.reportType")}
                  </th>
                  <th className="px-5 py-3 font-medium text-slate-500">
                    {t("schedules.lastRun")}
                  </th>
                  <th className="px-5 py-3 font-medium text-slate-500">
                    {t("common.status")}
                  </th>
                  <th className="px-5 py-3 font-medium text-slate-500">
                    {t("common.active")}
                  </th>
                  <th className="px-5 py-3 font-medium text-slate-500">
                    {t("common.actions")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {schedules.length === 0 ? (
                  <tr>
                    <td
                      colSpan={9}
                      className="px-5 py-8 text-center text-slate-400"
                    >
                      {t("schedules.noData")}
                    </td>
                  </tr>
                ) : (
                  schedules.map((schedule) => (
                    <tr
                      key={schedule.id}
                      className="border-b border-slate-50 hover:bg-slate-50"
                    >
                      <td className="px-5 py-3 font-medium text-slate-900">
                        {schedule.name}
                      </td>
                      <td className="px-5 py-3 text-slate-600">
                        {schedule.company?.name ?? t("schedules.allCompanies")}
                      </td>
                      <td className="px-5 py-3 text-slate-600">
                        {cronToHuman(schedule.cron_expression, t)}
                      </td>
                      <td className="px-5 py-3 text-slate-600">
                        <TargetBadge schedule={schedule} t={t} />
                      </td>
                      <td className="px-5 py-3 text-slate-600">
                        {t(`schedules.reportTypes.${schedule.report_type}`)}
                      </td>
                      <td className="px-5 py-3 text-slate-600 text-xs">
                        {schedule.last_run_at
                          ? new Date(schedule.last_run_at).toLocaleString()
                          : "—"}
                      </td>
                      <td className="px-5 py-3">
                        {schedule.last_run_status ? (
                          <StatusBadge status={schedule.last_run_status} />
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-5 py-3">
                        <button
                          onClick={() => handleToggleActive(schedule)}
                          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                            schedule.is_active ? "bg-blue-600" : "bg-slate-300"
                          }`}
                        >
                          <span
                            className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                              schedule.is_active
                                ? "translate-x-[18px]"
                                : "translate-x-[3px]"
                            }`}
                          />
                        </button>
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleRunNow(schedule.id)}
                            className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-emerald-600"
                            title={t("schedules.runNow")}
                          >
                            <Play className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => {
                              setEditing(schedule);
                              setShowForm(true);
                            }}
                            className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-blue-600"
                          >
                            <Pencil className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(schedule.id)}
                            className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-red-600"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Run History */}
          <div>
            <h2 className="text-lg font-semibold text-slate-900 mb-4">
              {t("schedules.runHistory")}
            </h2>
            <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left">
                    <th className="px-5 py-3 font-medium text-slate-500">
                      {t("reports.date")}
                    </th>
                    <th className="px-5 py-3 font-medium text-slate-500">
                      {t("reports.company")}
                    </th>
                    <th className="px-5 py-3 font-medium text-slate-500">
                      {t("reports.totalEmails")}
                    </th>
                    <th className="px-5 py-3 font-medium text-slate-500">
                      {t("reports.highPriority")}
                    </th>
                    <th className="px-5 py-3 font-medium text-slate-500">
                      {t("reports.status")}
                    </th>
                    <th className="px-5 py-3 font-medium text-slate-500">
                      {t("reports.telegram")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {runs.length === 0 ? (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-5 py-8 text-center text-slate-400"
                      >
                        {t("dashboard.noRuns")}
                      </td>
                    </tr>
                  ) : (
                    runs.map((run) => (
                      <tr
                        key={run.id}
                        className="border-b border-slate-50 hover:bg-slate-50"
                      >
                        <td className="px-5 py-3 text-slate-600 text-xs">
                          {new Date(run.started_at).toLocaleString()}
                        </td>
                        <td className="px-5 py-3 text-slate-600">
                          {run.company?.name ?? "—"}
                        </td>
                        <td className="px-5 py-3 text-slate-600">
                          {run.total_emails}
                        </td>
                        <td className="px-5 py-3 text-slate-600">
                          {run.high_priority}
                        </td>
                        <td className="px-5 py-3">
                          <StatusBadge status={run.status} />
                        </td>
                        <td className="px-5 py-3">
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                              run.telegram_delivered
                                ? "bg-emerald-50 text-emerald-700"
                                : "bg-slate-100 text-slate-500"
                            }`}
                          >
                            {run.telegram_delivered
                              ? t("dashboard.delivered")
                              : "—"}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {showForm && (
        <ScheduleForm
          schedule={editing}
          companies={companies}
          people={people}
          t={t}
          onClose={() => {
            setShowForm(false);
            setEditing(null);
          }}
          onSave={() => {
            setShowForm(false);
            setEditing(null);
            fetchData();
          }}
        />
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
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${styles[status] ?? "bg-slate-100 text-slate-600"}`}
    >
      {status}
    </span>
  );
}

function TargetBadge({
  schedule,
  t,
}: {
  schedule: DigestSchedule;
  t: (k: string) => string;
}) {
  if (schedule.target_type === "group") {
    return (
      <span className="text-xs">
        {t("schedules.targetGroup")}: {schedule.target_group_id ?? "—"}
      </span>
    );
  }
  if (schedule.target_type === "person") {
    return (
      <span className="text-xs">
        {schedule.target_person?.name ?? schedule.target_person_id ?? "—"}
      </span>
    );
  }
  return <span className="text-xs">{t("schedules.allMembers")}</span>;
}

function ScheduleForm({
  schedule,
  companies,
  people,
  t,
  onClose,
  onSave,
}: {
  schedule: DigestSchedule | null;
  companies: Company[];
  people: Person[];
  t: (key: string) => string;
  onClose: () => void;
  onSave: () => void;
}) {
  const [name, setName] = useState(schedule?.name ?? "");
  const [companyId, setCompanyId] = useState(schedule?.company_id ?? "");
  const [cronPreset, setCronPreset] = useState(() => {
    if (!schedule) return "0 8 * * *";
    const match = CRON_PRESETS.find(
      (p) => p.value !== "custom" && p.value === schedule.cron_expression
    );
    return match ? match.value : "custom";
  });
  const [customCron, setCustomCron] = useState(schedule?.cron_expression ?? "");
  const [timezone, setTimezone] = useState(
    schedule?.timezone ?? "America/Toronto"
  );
  const [targetType, setTargetType] = useState<
    "group" | "person" | "all_members"
  >(schedule?.target_type ?? "group");
  const [targetGroupId, setTargetGroupId] = useState(
    schedule?.target_group_id ?? ""
  );
  const [targetPersonId, setTargetPersonId] = useState(
    schedule?.target_person_id ?? ""
  );
  const [reportType, setReportType] = useState<"brief" | "full_docx" | "full_pdf" | "brief_with_docx" | "sync_only">(
    schedule?.report_type ?? "brief"
  );
  const [includeSections, setIncludeSections] = useState<string[]>(
    schedule?.include_sections ?? [
      "high_priority",
      "summary",
      "action_items",
    ]
  );
  const [lookbackDays, setLookbackDays] = useState(
    schedule?.lookback_days ?? 3
  );
  const [isActive, setIsActive] = useState(schedule?.is_active ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function toggleSection(section: string) {
    setIncludeSections((prev) =>
      prev.includes(section)
        ? prev.filter((s) => s !== section)
        : [...prev, section]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    const cronExpression =
      cronPreset === "custom" ? customCron : cronPreset;

    const payload = {
      id: schedule?.id,
      name,
      cron_expression: cronExpression,
      timezone,
      company_id: companyId || null,
      target_type: targetType,
      target_group_id: targetType === "group" ? targetGroupId || null : null,
      target_person_id: targetType === "person" ? targetPersonId || null : null,
      report_type: reportType,
      include_sections: includeSections,
      lookback_days: lookbackDays,
      is_active: isActive,
    };

    const res = await fetch("/api/schedules", {
      method: schedule ? "PUT" : "POST",
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
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900">
            {schedule
              ? t("schedules.editSchedule")
              : t("schedules.addSchedule")}
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:text-slate-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("schedules.name")}
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              required
            />
          </div>

          {/* Company */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("dashboard.company")}
            </label>
            <select
              value={companyId}
              onChange={(e) => setCompanyId(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              <option value="">{t("schedules.allCompanies")}</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Frequency */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("schedules.frequency")}
            </label>
            <select
              value={cronPreset}
              onChange={(e) => setCronPreset(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              {CRON_PRESETS.map((preset) => (
                <option key={preset.value} value={preset.value}>
                  {t(preset.labelKey)}
                </option>
              ))}
            </select>
            {cronPreset === "custom" && (
              <input
                type="text"
                value={customCron}
                onChange={(e) => setCustomCron(e.target.value)}
                placeholder="0 8 * * 1-5"
                className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                required
              />
            )}
          </div>

          {/* Timezone */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("schedules.timezone")}
            </label>
            <input
              type="text"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
          </div>

          {/* Target Type */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              {t("schedules.targetType")}
            </label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="radio"
                  name="target_type"
                  value="group"
                  checked={targetType === "group"}
                  onChange={() => setTargetType("group")}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500"
                />
                {t("schedules.targetGroup")}
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="radio"
                  name="target_type"
                  value="person"
                  checked={targetType === "person"}
                  onChange={() => setTargetType("person")}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500"
                />
                {t("schedules.targetPerson")}
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="radio"
                  name="target_type"
                  value="all_members"
                  checked={targetType === "all_members"}
                  onChange={() => setTargetType("all_members")}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500"
                />
                {t("schedules.allMembers")}
              </label>
            </div>
          </div>

          {/* Group ID input */}
          {targetType === "group" && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                {t("schedules.targetGroup")}
              </label>
              <input
                type="text"
                value={targetGroupId}
                onChange={(e) => setTargetGroupId(e.target.value)}
                placeholder="e.g. -1001234567890"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              />
            </div>
          )}

          {/* Person dropdown */}
          {targetType === "person" && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                {t("schedules.targetPerson")}
              </label>
              <select
                value={targetPersonId}
                onChange={(e) => setTargetPersonId(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              >
                <option value="">--</option>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.email})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Report Type */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("schedules.reportType")}
            </label>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value as "brief" | "full_docx" | "full_pdf" | "brief_with_docx" | "sync_only")}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              <option value="sync_only">
                {t("schedules.reportTypes.sync_only")}
              </option>
              <option value="brief">
                {t("schedules.reportTypes.brief")}
              </option>
              <option value="brief_with_docx">
                {t("schedules.reportTypes.brief_with_docx")}
              </option>
              <option value="full_docx">
                {t("schedules.reportTypes.full_docx")}
              </option>
              <option value="full_pdf">
                {t("schedules.reportTypes.full_pdf")}
              </option>
            </select>
          </div>

          {/* Include Sections */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              {t("schedules.sections")}
            </label>
            <div className="grid grid-cols-2 gap-1.5">
              {SECTION_OPTIONS.map((section) => (
                <label
                  key={section}
                  className="flex items-center gap-2 text-sm text-slate-600"
                >
                  <input
                    type="checkbox"
                    checked={includeSections.includes(section)}
                    onChange={() => toggleSection(section)}
                    className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  {t(`schedules.sections.${section}`)}
                </label>
              ))}
            </div>
          </div>

          {/* Lookback Days */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("schedules.lookbackDays")}
            </label>
            <input
              type="number"
              value={lookbackDays}
              onChange={(e) => setLookbackDays(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              min={1}
              max={30}
              required
            />
          </div>

          {/* Active */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="schedule_active"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <label
              htmlFor="schedule_active"
              className="text-sm text-slate-700"
            >
              {t("common.active")}
            </label>
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
