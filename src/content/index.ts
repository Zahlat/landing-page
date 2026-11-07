import { ar } from "./ar";
import { en } from "./en";
import type { SiteContent } from "./types";
import type { Locale } from "@/lib/i18n";

const dictionaries: Record<Locale, SiteContent> = { en, ar };

export function getContent(locale: Locale): SiteContent {
  return dictionaries[locale];
}
