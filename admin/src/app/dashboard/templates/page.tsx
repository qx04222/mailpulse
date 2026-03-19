"use client";

import { useEffect, useState, useCallback } from "react";
import { Plus, Pencil, Trash2, X, Eye } from "lucide-react";
import { useLocale } from "@/lib/i18n";
import type { Company } from "@/lib/types";

interface Template {
  id: string;
  name: string;
  subject: string;
  body: string;
  category: string;
  company_id: string | null;
  variables: string[];
  use_count: number;
  created_at: string;
  company?: { id: string; name: string } | null;
}

const CATEGORIES = [
  "reply",
  "follow_up",
  "introduction",
  "notification",
  "other",
];

export default function TemplatesPage() {
  const { t } = useLocale();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Template | null>(null);
  const [previewing, setPreviewing] = useState<Template | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const [tRes, cRes] = await Promise.all([
      fetch("/api/templates"),
      fetch("/api/companies"),
    ]);
    const tData = await tRes.json();
    const cData = await cRes.json();
    setTemplates(Array.isArray(tData) ? tData : []);
    setCompanies(Array.isArray(cData) ? cData : []);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleDelete(id: string) {
    if (!confirm(t("templates.confirmDelete"))) return;
    await fetch(`/api/templates?id=${id}`, { method: "DELETE" });
    fetchData();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          {t("templates.title")}
        </h1>
        <button
          onClick={() => {
            setEditing(null);
            setShowForm(true);
          }}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          {t("templates.addTemplate")}
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">
          {t("common.loading")}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left">
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("templates.templateName")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("templates.subject")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("templates.category")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("templates.company")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("templates.useCount")}
                </th>
                <th className="px-5 py-3 font-medium text-slate-500">
                  {t("common.actions")}
                </th>
              </tr>
            </thead>
            <tbody>
              {templates.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-5 py-8 text-center text-slate-400"
                  >
                    {t("templates.noData")}
                  </td>
                </tr>
              ) : (
                templates.map((tpl) => (
                  <tr
                    key={tpl.id}
                    className="border-b border-slate-50 hover:bg-slate-50"
                  >
                    <td className="px-5 py-3 font-medium text-slate-900">
                      {tpl.name}
                    </td>
                    <td className="px-5 py-3 text-slate-600">{tpl.subject}</td>
                    <td className="px-5 py-3">
                      <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                        {t(`templates.categories.${tpl.category}`) !==
                        `templates.categories.${tpl.category}`
                          ? t(`templates.categories.${tpl.category}`)
                          : tpl.category}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {tpl.company?.name ?? "—"}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {tpl.use_count ?? 0}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => setPreviewing(tpl)}
                          className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-violet-600"
                          title={t("templates.preview")}
                        >
                          <Eye className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => {
                            setEditing(tpl);
                            setShowForm(true);
                          }}
                          className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-blue-600"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(tpl.id)}
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
        <TemplateForm
          template={editing}
          companies={companies}
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

      {previewing && (
        <TemplatePreview
          template={previewing}
          t={t}
          onClose={() => setPreviewing(null)}
        />
      )}
    </div>
  );
}

function TemplateForm({
  template,
  companies,
  t,
  onClose,
  onSave,
}: {
  template: Template | null;
  companies: Company[];
  t: (key: string) => string;
  onClose: () => void;
  onSave: () => void;
}) {
  const [name, setName] = useState(template?.name ?? "");
  const [subject, setSubject] = useState(template?.subject ?? "");
  const [body, setBody] = useState(template?.body ?? "");
  const [category, setCategory] = useState(template?.category ?? "other");
  const [companyId, setCompanyId] = useState(template?.company_id ?? "");
  const [variables, setVariables] = useState(
    template?.variables?.join(", ") ?? ""
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    const payload = {
      id: template?.id,
      name,
      subject,
      body,
      category,
      company_id: companyId || null,
      variables: variables
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean),
    };

    const res = await fetch("/api/templates", {
      method: template ? "PUT" : "POST",
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
            {template ? t("templates.editTemplate") : t("templates.addTemplate")}
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
              {t("templates.templateName")}
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
              {t("templates.subject")}
            </label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("templates.body")}
            </label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={6}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("templates.category")}
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {t(`templates.categories.${cat}`) !==
                  `templates.categories.${cat}`
                    ? t(`templates.categories.${cat}`)
                    : cat}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("templates.company")}
            </label>
            <select
              value={companyId}
              onChange={(e) => setCompanyId(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              <option value="">{t("templates.allCompanies")}</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {t("templates.variables")}
            </label>
            <input
              type="text"
              value={variables}
              onChange={(e) => setVariables(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              placeholder="client_name, company_name, date"
            />
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

function TemplatePreview({
  template,
  t,
  onClose,
}: {
  template: Template;
  t: (key: string) => string;
  onClose: () => void;
}) {
  // Replace variables with sample values
  let previewBody = template.body;
  for (const v of template.variables ?? []) {
    previewBody = previewBody.replaceAll(
      `{{${v}}}`,
      `[${v.toUpperCase()}]`
    );
  }

  let previewSubject = template.subject;
  for (const v of template.variables ?? []) {
    previewSubject = previewSubject.replaceAll(
      `{{${v}}}`,
      `[${v.toUpperCase()}]`
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900">
            {t("templates.previewTitle")}
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:text-slate-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <p className="text-xs font-medium text-slate-500">
              {t("templates.subject")}
            </p>
            <p className="text-sm font-medium text-slate-900">
              {previewSubject}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500">
              {t("templates.body")}
            </p>
            <div className="mt-1 rounded-lg bg-slate-50 p-3 text-sm text-slate-800 whitespace-pre-wrap">
              {previewBody}
            </div>
          </div>
          {template.variables?.length > 0 && (
            <div>
              <p className="text-xs font-medium text-slate-500">
                {t("templates.variables")}
              </p>
              <div className="mt-1 flex flex-wrap gap-1">
                {template.variables.map((v) => (
                  <code
                    key={v}
                    className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600"
                  >
                    {`{{${v}}}`}
                  </code>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end mt-4">
          <button
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            {t("common.close")}
          </button>
        </div>
      </div>
    </div>
  );
}
