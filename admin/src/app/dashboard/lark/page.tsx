"use client";

import { useEffect, useState, useCallback } from "react";
import { CheckCircle, XCircle, RefreshCw, Save, Plus } from "lucide-react";
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

interface SyncStats {
  [companyId: string]: {
    base_count: number;
    calendar_count: number;
    last_sync: string | null;
  };
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
  const [syncStats, setSyncStats] = useState<SyncStats>({});
  const [addingTabs, setAddingTabs] = useState<string | null>(null);
  const [tabMsg, setTabMsg] = useState<{ id: string; msg: string; ok: boolean } | null>(null);

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

  const fetchSyncStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/lark", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "sync_status" }),
      });
      const data = await res.json();
      if (data.stats) {
        setSyncStats(data.stats);
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchData();
    fetchSyncStatus();
  }, [fetchData, fetchSyncStatus]);

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

  async function saveAll() {
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

  async function addTabs(company: CompanyMapping) {
    if (!company.lark_group_id) return;
    setAddingTabs(company.id);
    setTabMsg(null);
    try {
      const res = await fetch("/api/lark", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "create_tabs",
          chat_id: company.lark_group_id,
          company_name: company.name,
          app_token: company.lark_base_app_token,
          calendar_id: company.lark_calendar_id,
        }),
      });
      if (res.ok) {
        setTabMsg({ id: company.id, msg: t("lark.tabsAdded"), ok: true });
      } else {
        const data = await res.json();
        setTabMsg({ id: company.id, msg: data.error || t("lark.tabsError"), ok: false });
      }
    } catch {
      setTabMsg({ id: company.id, msg: t("lark.tabsError"), ok: false });
    }
    setAddingTabs(null);
    setTimeout(() => setTabMsg(null), 4000);
  }

  function formatLastSync(ts: string | null): string {
    if (!ts) return t("lark.noSync");
    const d = new Date(ts);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return t("events.ago.justNow");
    if (diffMin < 60) return `${diffMin}${t("events.ago.minutesAgo")}`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}${t("events.ago.hoursAgo")}`;
    const diffDay = Math.floor(diffHr / 24);
    return `${diffDay}${t("events.ago.daysAgo")}`;
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

      {/* Section 1: Connection Status */}
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
              {appIdPreview || "\u2014"}
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

      {/* Section 2: Per-Company Configuration */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-slate-900">
            {t("lark.perCompanyConfig")}
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
              onClick={saveAll}
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
          <div className="space-y-4">
            {companies.map((company) => {
              const stats = syncStats[company.id];
              return (
                <div
                  key={company.id}
                  className="rounded-lg border border-slate-200 p-4"
                >
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-slate-800">
                      {company.name}
                    </h3>
                    <div className="flex items-center gap-2">
                      {tabMsg && tabMsg.id === company.id && (
                        <span
                          className={`text-xs ${
                            tabMsg.ok ? "text-green-600" : "text-red-600"
                          }`}
                        >
                          {tabMsg.msg}
                        </span>
                      )}
                      <button
                        onClick={() => addTabs(company)}
                        disabled={
                          addingTabs === company.id ||
                          !company.lark_group_id ||
                          (!company.lark_base_app_token && !company.lark_calendar_id)
                        }
                        className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-40"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        {addingTabs === company.id ? "..." : t("lark.addTabs")}
                      </button>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {/* Lark Group ID */}
                    <div>
                      <label className="block text-xs font-medium text-slate-500 mb-1">
                        {t("lark.larkGroupId")}
                      </label>
                      <input
                        type="text"
                        value={company.lark_group_id || ""}
                        onChange={(e) =>
                          updateField(company.id, "lark_group_id", e.target.value)
                        }
                        placeholder="oc_xxxxxxxxxxxxxxxx"
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                      />
                    </div>

                    {/* Base App Token + Table ID side by side */}
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

                    {/* Calendar ID */}
                    <div>
                      <label className="block text-xs font-medium text-slate-500 mb-1">
                        {t("lark.calendarId")}
                      </label>
                      <input
                        type="text"
                        value={company.lark_calendar_id || ""}
                        onChange={(e) =>
                          updateField(company.id, "lark_calendar_id", e.target.value)
                        }
                        placeholder="feishu.calendar_xxxxxxxxxx"
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                      />
                    </div>

                    {/* Sync status row */}
                    <div className="flex items-center gap-4 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
                      <span>
                        {t("lark.baseRecords")}: <strong className="text-slate-700">{stats?.base_count ?? 0}</strong>
                      </span>
                      <span className="text-slate-300">|</span>
                      <span>
                        {t("lark.calendarEvents")}: <strong className="text-slate-700">{stats?.calendar_count ?? 0}</strong>
                      </span>
                      <span className="text-slate-300">|</span>
                      <span>
                        {t("lark.lastSync")}: <strong className="text-slate-700">{formatLastSync(stats?.last_sync ?? null)}</strong>
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Section 3: Card Preview */}
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-900 mb-4">
          {t("lark.cardPreview")}
        </h2>
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 font-mono text-sm leading-relaxed text-slate-700">
          <div className="rounded bg-red-600 px-3 py-2 mb-3">
            <p className="text-sm font-bold text-white">
              {"\uD83D\uDD34"} Arcview {"邮件周报"} {"·"} 03/17-03/20
            </p>
          </div>
          <div className="border-t border-slate-300 my-2" />
          <p>{"\uD83D\uDCCA"} Arcview {"·"} 03/17-03/20</p>
          <p>
            {"\uD83D\uDCE7"} {"邮件总数："}
            <strong>42</strong>
            {"　|　"}
            {"\uD83D\uDCAC"} {"对话线程："}
            <strong>15</strong>
          </p>
          <p>
            {"\uD83D\uDD34"} {"需立即处理："}
            <strong>3</strong>
            {"　|　"}
            {"\uD83D\uDFE1"} {"需关注："}
            <strong>8</strong>
            {"　|　"}
            {"\u26AA"} {"低优先："}
            <strong>7</strong>
          </p>
          <div className="border-t border-slate-300 my-2" />
          <p className="text-xs text-slate-500 italic mb-1">
            [{"每位负责人的分项报告..."}]
          </p>
          <div className="border-t border-slate-300 my-2" />
          <p className="font-bold">{"\uD83D\uDCCC"} {"重点行动项："}</p>
          <p>1. Niall Filewod {"—"} {"更新报价"} {"\u2192"} Belle</p>
          <p>2. GEM Windows {"—"} {"折叠门改双层"} {"\u2192"} Belle</p>
          <div className="border-t border-slate-300 my-2" />
          <p className="text-xs text-slate-400">
            MailPulse {"·"} 2026-03-20 10:00
          </p>
        </div>
      </div>
    </div>
  );
}
