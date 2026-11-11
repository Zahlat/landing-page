const configured = process.env.NEXT_PUBLIC_SITE_URL?.trim().replace(/\/+$/, "");

/** Public origin such as https://example.com. Undefined until a domain is configured. */
export const siteUrl = configured && /^https?:\/\//.test(configured) ? configured : undefined;

/** Indexable top-level paths, shared by the sitemap. "" is the home page. */
export const SITE_SECTIONS = ["", "/services", "/approach", "/about", "/contact"] as const;
