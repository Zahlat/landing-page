import type { Metadata } from "next";
import { getContent } from "@/content";
import { hrefFor, type Locale } from "@/lib/i18n";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL;
const metadataBase = siteUrl && /^https?:\/\//.test(siteUrl) ? new URL(siteUrl) : undefined;

export function localizedMetadata(locale: Locale, section: "home" | "services" | "approach" | "work" | "about" | "contact" = "home"): Metadata {
  const content = getContent(locale);
  const names = {
    home: "", services: content.navigation.services, approach: content.navigation.approach,
    work: content.navigation.work, about: content.navigation.about, contact: content.navigation.contact,
  };
  const pathname = section === "home" ? "" : `/${section}`;
  const title = section === "home" ? content.seo.title : `${names[section]} | Meraki`;
  return {
    title, description: content.seo.description,
    ...(metadataBase ? { metadataBase, alternates: {
      canonical: hrefFor(locale, pathname),
      languages: { en: hrefFor("en", pathname), ar: hrefFor("ar", pathname), "x-default": hrefFor("ar", pathname) },
    } } : {}),
    robots: { index: true, follow: true },
    openGraph: { title, description: content.seo.description, locale: locale === "ar" ? "ar_SY" : "en_US", type: "website", siteName: "Meraki" },
  };
}
