"use client";

import { useEffect, useState, useCallback } from "react";
import { Plus, Pencil, Trash2, X, UserPlus, UserMinus } from "lucide-react";
import { useLocale } from "@/lib/i18n";
import type { Company, Person } from "@/lib/types";

type CompanyWithMembers = Company & { members: Person[] };

export default function CompaniesPage() {
  const { t } = useLocale();
  const [companies, setCompanies] = useState<CompanyWithMembers[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<CompanyWithMembers | null>(null);
  const [managingMembers, setManagingMembers] = useState<CompanyWithMembers | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const [companiesRes, peopleRes] = await Promise.all([
      fetch("/api/companies"),
      fetch("/api/people"),
    ]);
    const companiesData = await companiesRes.json();
    const peopleData = await peopleRes.json();
    setCompanies(Array.isArray(companiesData) ? companiesData : []);
    setPeople(Array.isArray(peopleData) ? peopleData : []);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleDelete(id: string) {
    if (!confirm(t("companies.confirmDelete"))) return;
    await fetch(`/api/companies?id=${id}`, { method: "DELETE" });
    fetchData();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">{t("companies.title")}</h1>
        <button
          onClick={() => {
            setEditing(null);
            setShowForm(true);
          }}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          {t("companies.addCompany")}
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">{t("common.loading")}</div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left">
                <th className="px-5 py-3 font-medium text-slate-500">{t("companies.name")}</th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("companies.gmailLabel")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("companies.telegramGroup")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("common.active")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("companies.members")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("common.actions")}
                </th>
              </tr>
            </thead>
            <tbody>
              {companies.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-5 py-8 text-center text-slate-400"
                  >
                    {t("companies.noData")}
                  </td>
                </tr>
              ) : (
                companies.map((company) => (
                  <tr
                    key={company.id}
                    className="border-b border-slate-50 hover:bg-slate-50"
                  >
                    <td className="px-5 py-3 font-medium text-slate-900">
                      {company.name}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">
                        {company.gmail_label}
                      </code>
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      <div>
                        {company.lark_group_id ?? "—"}
                        {company.telegram_group_id && (
                          <div className="text-xs text-slate-400 mt-0.5">
                            TG: {company.telegram_group_id}
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          company.is_active
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {company.is_active ? t("common.active") : t("common.inactive")}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {company.members?.length ?? 0}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => setManagingMembers(company)}
                          className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-emerald-600"
                          title={t("companies.manageMembers")}
                        >
                          <UserPlus className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => {
                            setEditing(company);
                            setShowForm(true);
                          }}
                          className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-blue-600"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(company.id)}
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
        <CompanyForm
          company={editing}
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

      {managingMembers && (
        <MembersModal
          company={managingMembers}
          allPeople={people}
          t={t}
          onClose={() => setManagingMembers(null)}
          onUpdate={() => {
            setManagingMembers(null);
            fetchData();
          }}
        />
      )}
    </div>
  );
}

function CompanyForm({
  company,
  t,
  onClose,
  onSave,
}: {
  company: CompanyWithMembers | null;
  t: (key: string) => string;
  onClose: () => void;
  onSave: () => void;
}) {
  const [name, setName] = useState(company?.name ?? "");
  const [gmailLabel, setGmailLabel] = useState(company?.gmail_label ?? "");
  const [larkGroupId, setLarkGroupId] = useState(
    company?.lark_group_id ?? ""
  );
  const [telegramGroupId, setTelegramGroupId] = useState(
    company?.telegram_group_id ?? ""
  );
  const [isActive, setIsActive] = useState(company?.is_active ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    const payload = {
      id: company?.id,
      name,
      gmail_label: gmailLabel,
      lark_group_id: larkGroupId || null,
      telegram_group_id: telegramGroupId || null,
      is_active: isActive,
    };

    const res = await fetch("/api/companies", {
      method: company ? "PUT" : "POST",
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
            {company ? t("companies.editCompany") : t("companies.addCompany")}
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
              {t("companies.gmailLabel")}
            </label>
            <input
              type="text"
              value={gmailLabel}
              onChange={(e) => setGmailLabel(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("companies.telegramGroup")}
            </label>
            <input
              type="text"
              value={larkGroupId}
              onChange={(e) => setLarkGroupId(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              placeholder="oc_xxxxxxxxxxxx"
            />
            <p className="mt-1 text-xs text-slate-400">
              {t("companies.telegramGroupHelper")}
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              Telegram Group ID (legacy)
            </label>
            <input
              type="text"
              value={telegramGroupId}
              onChange={(e) => setTelegramGroupId(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              placeholder="Optional"
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="company_active"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <label
              htmlFor="company_active"
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

function MembersModal({
  company,
  allPeople,
  t,
  onClose,
  onUpdate,
}: {
  company: CompanyWithMembers;
  allPeople: Person[];
  t: (key: string) => string;
  onClose: () => void;
  onUpdate: () => void;
}) {
  const [working, setWorking] = useState<string | null>(null);

  const memberIds = new Set(company.members?.map((m) => m.id) ?? []);
  const nonMembers = allPeople.filter((p) => !memberIds.has(p.id));

  async function addMember(personId: string) {
    setWorking(personId);
    await fetch(`/api/companies/${company.id}/members`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "add", person_id: personId }),
    });
    onUpdate();
  }

  async function removeMember(personId: string) {
    setWorking(personId);
    await fetch(`/api/companies/${company.id}/members`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "remove", person_id: personId }),
    });
    onUpdate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900">
            {t("companies.membersOf").replace("{name}", company.name)}
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:text-slate-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Current Members */}
        <div className="mb-4">
          <h3 className="text-sm font-medium text-slate-500 mb-2">
            {t("companies.currentMembers")}
          </h3>
          {company.members?.length === 0 ? (
            <p className="text-sm text-slate-400">{t("companies.noMembers")}</p>
          ) : (
            <div className="space-y-1">
              {company.members?.map((member) => (
                <div
                  key={member.id}
                  className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-800">
                      {member.name}
                    </p>
                    <p className="text-xs text-slate-500">{member.email}</p>
                  </div>
                  <button
                    onClick={() => removeMember(member.id)}
                    disabled={working === member.id}
                    className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                  >
                    <UserMinus className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Add Members */}
        {nonMembers.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-slate-500 mb-2">
              {t("companies.addMembers")}
            </h3>
            <div className="space-y-1">
              {nonMembers.map((person) => (
                <div
                  key={person.id}
                  className="flex items-center justify-between rounded-lg border border-dashed border-slate-200 px-3 py-2"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-800">
                      {person.name}
                    </p>
                    <p className="text-xs text-slate-500">{person.email}</p>
                  </div>
                  <button
                    onClick={() => addMember(person.id)}
                    disabled={working === person.id}
                    className="rounded p-1 text-slate-400 hover:bg-emerald-50 hover:text-emerald-600 disabled:opacity-50"
                  >
                    <UserPlus className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-end mt-4">
          <button
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            {t("common.done")}
          </button>
        </div>
      </div>
    </div>
  );
}
