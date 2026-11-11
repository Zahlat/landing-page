import type { MetadataRoute } from "next";
import { hrefFor, locales } from "@/lib/i18n";
import { projects } from "@/lib/projects";
import { SITE_SECTIONS, siteUrl } from "@/lib/site";

// lastModified is left out on purpose: without a real edit date for each page, a made-up one
// only teaches search engines to ignore it.
export default function sitemap(): MetadataRoute.Sitemap {
  if (!siteUrl) return [];
  const origin = siteUrl;
  const paths: string[] = [
    ...SITE_SECTIONS,
    ...(projects.length > 0 ? ["/work", ...projects.map((project) => `/work/${project.slug}`)] : []),
  ];
  const urlFor = (locale: (typeof locales)[number], path: string) => `${origin}${hrefFor(locale, path)}`;
  return paths.flatMap((path) =>
    locales.map((locale) => ({
      url: urlFor(locale, path),
      alternates: { languages: { ar: urlFor("ar", path), en: urlFor("en", path), "x-default": urlFor("ar", path) } },
    })),
  );
}
