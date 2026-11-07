import { getWhatsAppHref, getWhatsAppDisplayNumber } from "@/lib/whatsapp";
import { getContent } from "@/content";
import type { Locale } from "@/lib/i18n";

type Props = { locale: Locale; variant?: "primary" | "light" };

export function WhatsAppCta({ locale, variant = "primary" }: Props) {
  const { contact } = getContent(locale);
  const href = getWhatsAppHref(locale);
  const displayedNumber = getWhatsAppDisplayNumber();
  if (!href) {
    return <span className="wa-pending" aria-label={contact.pending} title={contact.pendingDetail}>{contact.pending}</span>;
  }
  return (
    <div className="whatsapp-contact">
      <a className={`button button-${variant} whatsapp-button`} href={href} target="_blank" rel="noopener noreferrer">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20.4 11.6A8.4 8.4 0 0 1 8 19l-4.8 1.4 1.5-4.7A8.4 8.4 0 1 1 20.4 11.6Z"/><path d="M8.4 8.8c.4 2.7 2.3 4.7 5 5.3l1.1-1.3 2.4 1.1c-.3 1.2-1.2 2-2.4 2-4.4 0-8-3.5-8-7.5 0-1.2.7-2.3 1.9-2.6l1.2 2.4-1.1 1.2Z"/></svg>
        {contact.whatsapp}
        <span aria-hidden="true">↗</span>
      </a>
      {displayedNumber && <span className="whatsapp-number" dir="ltr">{displayedNumber}</span>}
    </div>
  );
}
