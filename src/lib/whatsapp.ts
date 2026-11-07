import type { Locale } from "./i18n";
import { getContent } from "@/content";

/** Public company contact. Syria domestic: 0991 953 560; international: +963 991 953 560. */
const DEFAULT_COMPANY_WHATSAPP = "963991953560";

/**
 * wa.me requires the international phone number, with country code and no '+'.
 * The company number is public contact information, not a secret.
 * A deployment environment variable can override it when the company changes its number.
 */
export function getWhatsAppNumber(): string | null {
  const configured = process.env.WHATSAPP_NUMBER || DEFAULT_COMPANY_WHATSAPP;
  const digits = configured.replace(/[\s()+-]/g, "");
  return /^[1-9]\d{7,14}$/.test(digits) ? digits : null;
}

/** Readable E.164 contact number; return null rather than displaying an invalid value. */
export function getWhatsAppDisplayNumber(): string | null {
  const number = getWhatsAppNumber();
  if (!number) return null;
  if (number.startsWith("963") && number.length === 12) {
    return `+963 ${number.slice(3, 6)} ${number.slice(6, 9)} ${number.slice(9)}`;
  }
  return `+${number}`;
}

/** Localized pre-filled message, URL-encoded correctly for Arabic and English. */
export function getWhatsAppHref(locale: Locale): string | null {
  const number = getWhatsAppNumber();
  if (!number) return null;
  const text = getContent(locale).contact.message;
  return `https://wa.me/${number}?${new URLSearchParams({ text })}`;
}
