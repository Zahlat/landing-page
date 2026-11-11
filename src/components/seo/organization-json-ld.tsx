import { getContent } from "@/content";
import type { Locale } from "@/lib/i18n";
import { siteUrl } from "@/lib/site";
import { getWhatsAppNumber } from "@/lib/whatsapp";

/** Only facts the site already states. Add sameAs and an address once they are real. */
export function OrganizationJsonLd({ locale }: { locale: Locale }) {
  if (!siteUrl) return null;
  const { seo } = getContent(locale);
  const whatsapp = getWhatsAppNumber();
  const organizationId = `${siteUrl}/#organization`;
  const data = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": organizationId,
        name: "Meraki",
        alternateName: "ميراكي",
        url: siteUrl,
        logo: `${siteUrl}/brand/logo-512.png`,
        description: seo.description,
        areaServed: [{ "@type": "Country", name: "Syria" }],
        ...(whatsapp ? {
          contactPoint: { "@type": "ContactPoint", contactType: "customer service", telephone: `+${whatsapp}`, availableLanguage: ["ar", "en"] },
        } : {}),
      },
      {
        "@type": "WebSite",
        "@id": `${siteUrl}/#website`,
        name: locale === "ar" ? "ميراكي" : "Meraki",
        url: `${siteUrl}/${locale}`,
        inLanguage: locale,
        publisher: { "@id": organizationId },
      },
    ],
  };
  // Replacing "<" stops any value from closing the script element.
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, "\\u003c") }}/>;
}
