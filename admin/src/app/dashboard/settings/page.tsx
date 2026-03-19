"use client";

import { useEffect, useState } from "react";
import { useLocale } from "@/lib/i18n";

export default function SettingsPage() {
  const { locale, setLocale, t } = useLocale();
  const [lastRun, setLastRun] = useState<string | null>(null);
  const [totalRuns, setTotalRuns] = useState(0);

  useEffect(() => {
    async function fetchInfo() {
      try {
        const res = await fetch("/api/reports");
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          setLastRun(data[0].started_at);
          setTotalRuns(data.length);
        }
      } catch {
        // ignore
      }
    }
    fetchInfo();
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">
        {t("settings.title")}
      </h1>

      <div className="space-y-6 max-w-lg">
        {/* Language */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-base font-semibold text-slate-900 mb-3">
            {t("settings.language")}
          </h2>
          <div className="flex gap-2">
            <button
              onClick={() => setLocale("zh")}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                locale === "zh"
                  ? "bg-blue-600 text-white"
                  : "border border-slate-300 text-slate-700 hover:bg-slate-50"
              }`}
            >
              {t("settings.languageZh")}
            </button>
            <button
              onClick={() => setLocale("en")}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                locale === "en"
                  ? "bg-blue-600 text-white"
                  : "border border-slate-300 text-slate-700 hover:bg-slate-50"
              }`}
            >
              {t("settings.languageEn")}
            </button>
          </div>
        </div>

        {/* System Info */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-base font-semibold text-slate-900 mb-3">
            {t("settings.systemInfo")}
          </h2>
          <div className="space-y-2.5">
            <InfoField label={t("settings.version")} value="0.1.0" />
            <InfoField
              label={t("settings.lastDigestRun")}
              value={
                lastRun
                  ? new Date(lastRun).toLocaleString()
                  : "—"
              }
            />
            <InfoField
              label={t("settings.totalDigestRuns")}
              value={String(totalRuns)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-sm font-medium text-slate-800">{value}</p>
    </div>
  );
}
