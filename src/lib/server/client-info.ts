import "server-only";
import { headers } from "next/headers";

const USER_AGENT_MAX = 512;
let warnedMissingHeader = false;

export type ClientInfo = { ip: string | null; userAgent: string | null };

/**
 * Visitor IP and user agent for rate limiting.
 *
 * The IP comes only from the header named by TRUSTED_CLIENT_IP_HEADER, which must be one
 * the hosting platform overwrites on every request (for example cf-connecting-ip).
 * X-Forwarded-For is never read by default because visitors can forge its left-most value.
 * With no header configured the IP is omitted and FastAPI uses one shared "unknown" bucket.
 */
export async function getClientInfo(): Promise<ClientInfo> {
  const requestHeaders = await headers();
  const headerName = process.env.TRUSTED_CLIENT_IP_HEADER?.trim();
  if (!headerName && process.env.NODE_ENV === "production" && !warnedMissingHeader) {
    warnedMissingHeader = true;
    console.warn("TRUSTED_CLIENT_IP_HEADER is not set: all visitors share one rate-limit bucket");
  }
  return {
    ip: headerName ? requestHeaders.get(headerName)?.trim() || null : null,
    userAgent: requestHeaders.get("user-agent")?.slice(0, USER_AGENT_MAX) || null,
  };
}

/** Headers FastAPI expects; a missing value is left out rather than sent empty. */
export function clientInfoHeaders(client: ClientInfo): Record<string, string> {
  return {
    ...(client.ip ? { "X-Client-IP": client.ip } : {}),
    ...(client.userAgent ? { "X-Client-UA": client.userAgent } : {}),
  };
}
