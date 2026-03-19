"use client";

import { createContext, useContext } from "react";
import zh from "./zh";
import en from "./en";

export type Locale = "zh" | "en";

const translations: Record<Locale, Record<string, string>> = { zh, en };

export function translate(locale: Locale, key: string): string {
  return translations[locale]?.[key] ?? key;
}

export interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string) => string;
}

export const LocaleContext = createContext<LocaleContextValue>({
  locale: "zh",
  setLocale: () => {},
  t: (key: string) => translate("zh", key),
});

export function useLocale() {
  return useContext(LocaleContext);
}
