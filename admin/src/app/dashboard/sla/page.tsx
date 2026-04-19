"use client";

import { useEffect, useState, useCallback } from "react";
import { Pencil, X, Plus } from "lucide-react";
import { useLocale } from "@/lib/i18n";
import type { Company, Person } from "@/lib/types";

interface SlaConfig {
  id: string;
  company_id: string;
  first_response_hours: number;
  followup_response_hours: number;
  escalate_after_hours: number;
  escalate_to_id: string | null;
  created_at: string;
  company?: { id: string; name: string } | null;
}

export default function SlaPage() {
  const { t } = useLocale();
  const [configs, setConfigs] = useState<SlaConfig[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<SlaConfig | null>(null);
  const [showForm, setShowForm] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const [slaRes, compRes, peopleRes] = await Promise.all([
      fetch("/api/sla"),
      fetch("/api/companies"),
      fetch("/api/people"),
    ]);
    const slaData = await slaRes.json();
    const compData = await compRes.json();
    const peopleData = await peopleRes.json();
    setConfigs(Array.isArray(slaData) ? slaData : []);
    setCompanies(Array.isArray(compData) ? compData : []);
    setPeople(Array.isArray(peopleData) ? peopleData : []);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const configuredCompanyIds = new Set(configs.map((c) => c.company_id));
  const unconfiguredCompanies = companies.filter(
    (c) => !configuredCompanyIds.has(c.id)
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          {t("sla.title")}
        </h1>
        {unconfiguredCompanies.length > 0 && (
          <button
            onClick={() => {
              setEditing(null);
              setShowForm(true);
            }}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            {t("sla.createConfig")}
          </button>
        )}
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">
          {t("common.loading")}
        </div>
      ) : configs.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white px-5 py-12 text-center text-slate-400">
          {t("sla.noConfig")}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {configs.map((config) => (
            <div
              key={config.id}
              className="rounded-xl border border-slate-200 bg-white p-5"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-semibold text-slate-900">
                  {config.company?.name ?? "—"}
                </h3>
                <button
                  onClick={() => {
                    setEditing(config);
                    setShowForm(true);
                  }}
                  className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-blue-600"
                >
                  <Pencil className="h-4 w-4" />
                </button>
              </div>

              <div className="space-y-2.5">
                <SlaField
                  label={t("sla.firstResponse")}
                  value={`${config.first_response_hours} ${t("sla.hours")}`}
                />
                <SlaField
                  label={t("sla.followupResponse")}
                  value={`${config.followup_response_hours} ${t("sla.hours")}`}
                />
                <SlaField
                  label={t("sla.escalateAfter")}
                  value={`${config.escalate_after_hours} ${t("sla.hours")}`}
                />
                <SlaField
                  label={t("sla.escalateTo")}
                  value={
                    config.escalate_to_id
                      ? people.find((p) => p.id === config.escalate_to_id)?.name ??
                        config.escalate_to_id
                      : "—"
                  }
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <SlaForm
          config={editing}
          companies={editing ? companies : unconfiguredCompanies}
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

function SlaField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="text-sm text-slate-800">{value}</p>
    </div>
  );
}

function SlaForm({
  config,
  companies,
  people,
  t,
  onClose,
  onSave,
}: {
  config: SlaConfig | null;
  companies: Company[];
  people: Person[];
  t: (key: string) => string;
  onClose: () => void;
  onSave: () => void;
}) {
  const [companyId, setCompanyId] = useState(config?.company_id ?? "");
  const [firstResponse, setFirstResponse] = useState(
    config?.first_response_hours ?? 4
  );
  const [followup, setFollowup] = useState(
    config?.followup_response_hours ?? 24
  );
  const [escalateAfter, setEscalateAfter] = useState(
    config?.escalate_after_hours ?? 48
  );
  const [escalateTo, setEscalateTo] = useState(config?.escalate_to_id ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    const payload = {
      id: config?.id,
      company_id: companyId,
      first_response_hours: firstResponse,
      followup_response_hours: followup,
      escalate_after_hours: escalateAfter,
      escalate_to_id: escalateTo || null,
    };

    const res = await fetch("/api/sla", {
      method: config ? "PUT" : "POST",
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
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900">
            {config ? t("sla.editConfig") : t("sla.createConfig")}
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
              {t("companies.name")}
            </label>
            <select
              value={companyId}
              onChange={(e) => setCompanyId(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              required
              disabled={!!config}
            >
              <option value="">--</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("sla.firstResponse")} ({t("sla.hours")})
            </label>
            <input
              type="number"
              value={firstResponse}
              onChange={(e) => setFirstResponse(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              min={1}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("sla.followupResponse")} ({t("sla.hours")})
            </label>
            <input
              type="number"
              value={followup}
              onChange={(e) => setFollowup(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              min={1}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("sla.escalateAfter")} ({t("sla.hours")})
            </label>
            <input
              type="number"
              value={escalateAfter}
              onChange={(e) => setEscalateAfter(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              min={1}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("sla.escalateTo")}
            </label>
            <select
              value={escalateTo}
              onChange={(e) => setEscalateTo(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              <option value="">—</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
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
