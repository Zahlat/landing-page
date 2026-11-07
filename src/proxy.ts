import { NextResponse, type NextRequest } from "next/server";

/** Only / needs detection. All content pages have explicit /en or /ar prefixes. */
export function proxy(request: NextRequest) {
  const header = request.headers.get("accept-language") || "";
  const preferred = header.split(",").map((chunk) => {
    const [tag, ...props] = chunk.trim().split(";");
    const q = props.find((part) => part.trim().startsWith("q="));
    return { tag: tag?.toLowerCase() ?? "", quality: q ? Number(q.split("=")[1]) : 1 };
  }).filter((part) => Number.isFinite(part.quality)).sort((a, b) => b.quality - a.quality);
  const lang = preferred.find((part) => part.tag === "ar" || part.tag.startsWith("ar-"))?.quality;
  const english = preferred.find((part) => part.tag === "en" || part.tag.startsWith("en-"))?.quality;
  // Arabic is the primary audience: default to /ar for ties and unknown languages.
  const chosen = english !== undefined && (lang === undefined || english > lang) ? "en" : "ar";
  const response = NextResponse.redirect(new URL(`/${chosen}`, request.url));
  response.headers.set("Vary", "Accept-Language");
  return response;
}
export const config = { matcher: ["/"] };
