import type { Metadata } from "next";
import { getContent } from "@/content";
import { hrefFor, type Locale } from "@/lib/i18n";
import { projects } from "@/lib/projects";
import { siteUrl } from "@/lib/site";

type Section = "home" | "services" | "approach" | "work" | "about" | "contact";
type Overrides = { path?: string; title?: string; description?: string; index?: boolean };

const metadataBase = siteUrl ? new URL(siteUrl) : undefined;

export function localizedMetadata(locale: Locale, section: Section = "home", overrides: Overrides = {}): Metadata {
  const { seo } = getContent(locale);
  const page = section === "home" ? seo : seo.pages[section];
  const title = overrides.title ?? page.title;
  const description = overrides.description ?? page.description;
  const pathname = overrides.path ?? (section === "home" ? "" : `/${section}`);
  // An empty portfolio is thin content, so it stays out of search until a project exists.
  const index = overrides.index ?? !(section === "work" && projects.length === 0);
  const image = { url: `/og/og-${locale}.png`, width: 1200, height: 630, alt: title };

  return {
    title,
    description,
    robots: { index, follow: true },
    openGraph: {
      title,
      description,
      type: "website",
      siteName: locale === "ar" ? "ميراكي" : "Meraki",
      locale: locale === "ar" ? "ar_SY" : "en_US",
      alternateLocale: locale === "ar" ? ["en_US"] : ["ar_SY"],
      ...(metadataBase ? { url: hrefFor(locale, pathname), images: [image] } : {}),
    },
    twitter: { card: "summary_large_image", title, description, ...(metadataBase ? { images: [image.url] } : {}) },
    ...(metadataBase ? {
      metadataBase,
      alternates: {
        canonical: hrefFor(locale, pathname),
        languages: { ar: hrefFor("ar", pathname), en: hrefFor("en", pathname), "x-default": hrefFor("ar", pathname) },
      },
    } : {}),
  };
}
