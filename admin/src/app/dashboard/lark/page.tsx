"use client";

import { useEffect, useState, useCallback } from "react";
import { CheckCircle, XCircle, RefreshCw, Save } from "lucide-react";
import { useLocale } from "@/lib/i18n";

interface LarkChat {
  chat_id: string;
  name: string;
}

interface CompanyMapping {
  id: string;
  name: string;
  lark_group_id: string | null;
  lark_base_app_token: string | null;
  lark_base_table_id: string | null;
  lark_calendar_id: string | null;
}

interface ConnectionStatus {
  connected: boolean;
  token_preview?: string;
  chat_count?: number;
  chats?: LarkChat[];
  error?: string;
}

export default function LarkPage() {
  const { t } = useLocale();
  const [configured, setConfigured] = useState(false);
  const [appIdPreview, setAppIdPreview] = useState("");
  const [companies, setCompanies] = useState<CompanyMapping[]>([]);
  const [connection, setConnection] = useState<ConnectionStatus | null>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/lark");
      const data = await res.json();
      setConfigured(data.configured);
      setAppIdPreview(data.app_id || "");
      setCompanies(data.companies || []);
    } catch {
      // ignore
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function testConnection() {
    setTesting(true);
    setConnection(null);
    try {
      const res = await fetch("/api/lark", { method: "POST" });
      const data = await res.json();
      setConnection(data);
    } catch {
      setConnection({ connected: false, error: "Network error" });
    }
    setTesting(false);
  }

  function updateField(companyId: string, field: keyof CompanyMapping, value: string) {
    setCompanies((prev) =>
      prev.map((c) =>
        c.id === companyId ? { ...c, [field]: value || null } : c
      )
    );
  }

  async function saveGroupMappings() {
    setSaving(true);
    setSaveMsg("");
    try {
      const res = await fetch("/api/lark", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          companies: companies.map((c) => ({
            id: c.id,
            lark_group_id: c.lark_group_id,
            lark_base_app_token: c.lark_base_app_token,
            lark_base_table_id: c.lark_base_table_id,
            lark_calendar_id: c.lark_calendar_id,
          })),
        }),
      });
      if (res.ok) {
        setSaveMsg(t("lark.saveSuccess"));
      } else {
        const data = await res.json();
        setSaveMsg(data.error || t("lark.saveError"));
      }
    } catch {
      setSaveMsg(t("lark.saveError"));
    }
    setSaving(false);
    setTimeout(() => setSaveMsg(""), 3000);
  }

  if (loading) {
    return (
      <div className="text-center py-12 text-slate-400">
        {t("common.loading")}
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">
        {t("lark.title")}
      </h1>

      {/* Connection Status */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-slate-900">
            {t("lark.connection")}
          </h2>
          <button
            onClick={testConnection}
            disabled={testing || !configured}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw
              className={`h-4 w-4 ${testing ? "animate-spin" : ""}`}
            />
            {testing ? t("lark.testing") : t("lark.testConnection")}
          </button>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-500">App ID:</span>
            <span className="text-sm font-mono text-slate-700">
              {appIdPreview || "—"}
            </span>
          </div>

          {connection && (
            <div className="mt-3 space-y-2">
              <div className="flex items-center gap-2">
                {connection.connected ? (
                  <CheckCircle className="h-5 w-5 text-green-500" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-500" />
                )}
                <span
                  className={`text-sm font-medium ${
                    connection.connected ? "text-green-700" : "text-red-700"
                  }`}
                >
                  {connection.connected
                    ? t("lark.connected")
                    : t("lark.disconnected")}
                </span>
              </div>

              {connection.error && (
                <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
                  {connection.error}
                </div>
              )}

              {connection.connected && (
                <div className="space-y-1">
                  <p className="text-sm text-slate-500">
                    {t("lark.chatCount")}: {connection.chat_count}
                  </p>
                  {connection.chats && connection.chats.length > 0 ? (
                    <div className="mt-2">
                      <p className="text-xs font-medium text-slate-500 mb-1">
                        {t("lark.chats")}:
                      </p>
                      <div className="space-y-1">
                        {connection.chats.map((chat) => (
                          <div
                            key={chat.chat_id}
                            className="flex items-center gap-2 rounded bg-slate-50 px-3 py-1.5 text-sm"
                          >
                            <span className="text-slate-700">{chat.name}</span>
                            <span className="font-mono text-xs text-slate-400">
                              {chat.chat_id}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-400">
                      {t("lark.noChats")}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Group Mapping */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-slate-900">
            {t("lark.groupMapping")}
          </h2>
          <div className="flex items-center gap-2">
            {saveMsg && (
              <span
                className={`text-sm ${
                  saveMsg === t("lark.saveSuccess")
                    ? "text-green-600"
                    : "text-red-600"
                }`}
              >
                {saveMsg}
              </span>
            )}
            <button
              onClick={saveGroupMappings}
              disabled={saving}
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              {saving ? t("common.saving") : t("common.save")}
            </button>
          </div>
        </div>

        {companies.length === 0 ? (
          <p className="text-sm text-slate-400">{t("common.noData")}</p>
        ) : (
          <div className="space-y-3">
            {companies.map((company) => (
              <div
                key={company.id}
                className="flex items-center gap-4 rounded-lg border border-slate-100 p-3"
              >
                <div className="w-40">
                  <p className="text-sm font-medium text-slate-800">
                    {company.name}
                  </p>
                </div>
                <div className="flex-1">
                  <input
                    type="text"
                    value={company.lark_group_id || ""}
                    onChange={(e) =>
                      updateField(company.id, "lark_group_id", e.target.value)
                    }
                    placeholder={t("lark.larkGroupId")}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Card Preview */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 mb-6">
        <h2 className="text-base font-semibold text-slate-900 mb-4">
          {t("lark.cardPreview")}
        </h2>
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
          <div className="rounded bg-blue-600 px-3 py-2 mb-3">
            <p className="text-sm font-medium text-white">
              Company Digest | 03/17-03/20
            </p>
          </div>
          <div className="space-y-2 text-sm text-slate-700">
            <p>
              <strong>Company Name</strong> - 03/17-03/20
            </p>
            <p>
              Total emails: <strong>42</strong> | Threads: <strong>15</strong>
            </p>
            <p>
              High priority: <strong>3</strong> | Needs attention:{" "}
              <strong>8</strong> | Low: <strong>7</strong>
            </p>
            <hr className="border-slate-200 my-2" />
            <p className="text-xs text-slate-500 italic">
              Interactive cards with action buttons (Mark Done, Assign, Create
              Calendar, View Details) will be sent for each high-priority thread.
            </p>
          </div>
        </div>
      </div>

      {/* Lark Base Sync Settings */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 mb-6">
        <h2 className="text-base font-semibold text-slate-900 mb-4">
          {t("lark.baseSync")}
        </h2>
        <p className="text-sm text-slate-500 mb-4">
          {t("lark.baseSyncDesc")}
        </p>
        {companies.length > 0 && (
          <div className="space-y-3">
            {companies.map((company) => (
              <div
                key={`base-${company.id}`}
                className="rounded-lg border border-slate-100 p-3"
              >
                <p className="text-sm font-medium text-slate-800 mb-2">
                  {company.name}
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">
                      {t("lark.appToken")}
                    </label>
                    <input
                      type="text"
                      value={company.lark_base_app_token || ""}
                      onChange={(e) =>
                        updateField(company.id, "lark_base_app_token", e.target.value)
                      }
                      placeholder="bascnXXXXXXXXXX"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">
                      {t("lark.tableId")}
                    </label>
                    <input
                      type="text"
                      value={company.lark_base_table_id || ""}
                      onChange={(e) =>
                        updateField(company.id, "lark_base_table_id", e.target.value)
                      }
                      placeholder="tblXXXXXXXXXXXX"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Calendar Sync Settings */}
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-900 mb-4">
          {t("lark.calendarSync")}
        </h2>
        <p className="text-sm text-slate-500 mb-4">
          {t("lark.calendarSyncDesc")}
        </p>
        {companies.length > 0 && (
          <div className="space-y-3">
            {companies.map((company) => (
              <div
                key={`cal-${company.id}`}
                className="flex items-center gap-4 rounded-lg border border-slate-100 p-3"
              >
                <div className="w-40">
                  <p className="text-sm font-medium text-slate-800">
                    {company.name}
                  </p>
                </div>
                <div className="flex-1">
                  <input
                    type="text"
                    value={company.lark_calendar_id || ""}
                    onChange={(e) =>
                      updateField(company.id, "lark_calendar_id", e.target.value)
                    }
                    placeholder={t("lark.calendarId")}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
