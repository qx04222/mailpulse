"use client";

import { useEffect, useState, useCallback } from "react";
import { Plus, Pencil, Trash2, X } from "lucide-react";
import { useLocale } from "@/lib/i18n";
import type { Person, Company } from "@/lib/types";

type PersonWithCompanies = Person & { companies: Company[] };

export default function PeoplePage() {
  const { t } = useLocale();
  const [people, setPeople] = useState<PersonWithCompanies[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<PersonWithCompanies | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const [peopleRes, companiesRes] = await Promise.all([
      fetch("/api/people"),
      fetch("/api/companies"),
    ]);
    const peopleData = await peopleRes.json();
    const companiesData = await companiesRes.json();
    setPeople(Array.isArray(peopleData) ? peopleData : []);
    setCompanies(Array.isArray(companiesData) ? companiesData : []);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleDelete(id: string) {
    if (!confirm(t("people.confirmDelete"))) return;
    await fetch(`/api/people?id=${id}`, { method: "DELETE" });
    fetchData();
  }

  function openEdit(person: PersonWithCompanies) {
    setEditing(person);
    setShowForm(true);
  }

  function openAdd() {
    setEditing(null);
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    setEditing(null);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">{t("people.title")}</h1>
        <button
          onClick={openAdd}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          {t("people.addPerson")}
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">{t("common.loading")}</div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left">
                <th className="px-5 py-3 font-medium text-slate-500">{t("people.name")}</th>
                <th className="px-5 py-3 font-medium text-slate-500">{t("people.email")}</th>
                <th className="px-5 py-3 font-medium text-slate-500">{t("people.role")}</th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("people.telegram")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("people.active")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("people.companies")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("common.actions")}
                </th>
              </tr>
            </thead>
            <tbody>
              {people.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-5 py-8 text-center text-slate-400"
                  >
                    {t("people.noData")}
                  </td>
                </tr>
              ) : (
                people.map((person) => (
                  <tr
                    key={person.id}
                    className="border-b border-slate-50 hover:bg-slate-50"
                  >
                    <td className="px-5 py-3 font-medium text-slate-900">
                      {person.name}
                    </td>
                    <td className="px-5 py-3 text-slate-600">{person.email}</td>
                    <td className="px-5 py-3">
                      <RoleBadge role={person.role} t={t} />
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {person.telegram_user_id ?? "—"}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          person.is_active
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {person.is_active ? t("common.active") : t("common.inactive")}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {person.companies?.map((c) => c.name).join(", ") || "—"}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => openEdit(person)}
                          className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-blue-600"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(person.id)}
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
      )}

      {showForm && (
        <PersonForm
          person={editing}
          companies={companies}
          t={t}
          onClose={closeForm}
          onSave={() => {
            closeForm();
            fetchData();
          }}
        />
      )}
    </div>
  );
}

function RoleBadge({ role, t }: { role: string; t: (key: string) => string }) {
  const styles: Record<string, string> = {
    owner: "bg-violet-50 text-violet-700",
    manager: "bg-blue-50 text-blue-700",
    member: "bg-slate-100 text-slate-600",
  };
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[role] ?? "bg-slate-100 text-slate-600"}`}
    >
      {t(`people.roles.${role}`)}
    </span>
  );
}

function PersonForm({
  person,
  companies,
  t,
  onClose,
  onSave,
}: {
  person: PersonWithCompanies | null;
  companies: Company[];
  t: (key: string) => string;
  onClose: () => void;
  onSave: () => void;
}) {
  const [name, setName] = useState(person?.name ?? "");
  const [email, setEmail] = useState(person?.email ?? "");
  const [role, setRole] = useState(person?.role ?? "member");
  const [telegramUserId, setTelegramUserId] = useState(
    person?.telegram_user_id ?? ""
  );
  const [isActive, setIsActive] = useState(person?.is_active ?? true);
  const [selectedCompanies, setSelectedCompanies] = useState<string[]>(
    person?.companies?.map((c) => c.id) ?? []
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    const payload = {
      id: person?.id,
      name,
      email,
      role,
      telegram_user_id: telegramUserId || null,
      is_active: isActive,
      company_ids: selectedCompanies,
    };

    const res = await fetch("/api/people", {
      method: person ? "PUT" : "POST",
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

  function toggleCompany(id: string) {
    setSelectedCompanies((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900">
            {person ? t("people.editPerson") : t("people.addPerson")}
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
              {t("people.name")}
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("people.email")}
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("people.role")}
            </label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as Person["role"])}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              <option value="owner">{t("people.roles.owner")}</option>
              <option value="manager">{t("people.roles.manager")}</option>
              <option value="member">{t("people.roles.member")}</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("people.telegram")}
            </label>
            <input
              type="text"
              value={telegramUserId}
              onChange={(e) => setTelegramUserId(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              placeholder="Optional"
            />
            <p className="mt-1 text-xs text-slate-400">
              {t("people.telegramHelper")}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_active"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="is_active" className="text-sm text-slate-700">
              {t("people.active")}
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              {t("people.companies")}
            </label>
            <div className="space-y-1.5 max-h-32 overflow-y-auto">
              {companies.map((company) => (
                <label
                  key={company.id}
                  className="flex items-center gap-2 text-sm text-slate-600"
                >
                  <input
                    type="checkbox"
                    checked={selectedCompanies.includes(company.id)}
                    onChange={() => toggleCompany(company.id)}
                    className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  {company.name}
                </label>
              ))}
              {companies.length === 0 && (
                <p className="text-sm text-slate-400">{t("people.noCompanies")}</p>
              )}
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
