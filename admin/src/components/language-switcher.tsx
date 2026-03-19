"use client";

import { useLocale } from "@/lib/i18n";

export default function LanguageSwitcher() {
  const { locale, setLocale } = useLocale();

  return (
    <button
      onClick={() => setLocale(locale === "zh" ? "en" : "zh")}
      className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
    >
      <span className={locale === "zh" ? "text-blue-400" : ""}>中</span>
      <span className="text-slate-600">/</span>
      <span className={locale === "en" ? "text-blue-400" : ""}>EN</span>
    </button>
  );
}
