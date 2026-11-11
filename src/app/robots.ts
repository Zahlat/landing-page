import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/site";

// /admin is deliberately not listed. Blocking it here would stop crawlers from seeing its
// noindex header, and would publish the path. next.config.ts sets X-Robots-Tag on /admin.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    ...(siteUrl ? { sitemap: `${siteUrl}/sitemap.xml` } : {}),
  };
}
