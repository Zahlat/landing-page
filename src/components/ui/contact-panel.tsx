import type { Locale } from "@/lib/i18n";
import { getContent } from "@/content";
import { WhatsAppCta } from "./whatsapp-cta";

export function ContactPanel({ locale }: { locale: Locale }) {
  const { contact } = getContent(locale);
  return <section className="contact-panel" id="contact"><div className="container contact-inner"><div><p className="eyebrow eyebrow-light"><span className="eyebrow-square"/>{contact.eyebrow}</p><h2>{contact.heading}</h2><p>{contact.description}</p></div><div className="contact-action"><WhatsAppCta locale={locale} variant="light"/><span className="contact-handdrawn" aria-hidden="true">✳</span></div></div></section>;
}
