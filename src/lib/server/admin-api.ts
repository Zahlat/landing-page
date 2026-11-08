import "server-only";
import type { AdminFilters, MessageDetail, MessagePage, MessageStats } from "@/lib/admin-types";
import { adminFetch } from "@/lib/server/admin-session";

const PAGE_SIZE = "20";
const MESSAGES = "/v1/admin/messages";

export async function fetchMessagePage(filters: AdminFilters, cursor?: string): Promise<MessagePage | null> {
  const query = new URLSearchParams({ limit: PAGE_SIZE });
  if (filters.status) query.set("status", filters.status);
  if (filters.type) query.set("type", filters.type);
  if (cursor) query.set("cursor", cursor);
  const result = await adminFetch(`${MESSAGES}?${query}`, { method: "GET" });
  return result.kind === "ok" ? (result.data as MessagePage) : null;
}

export async function fetchMessageStats(): Promise<MessageStats | null> {
  const result = await adminFetch(`${MESSAGES}/stats`, { method: "GET" });
  return result.kind === "ok" ? (result.data as MessageStats) : null;
}

export type DetailResult = { kind: "found"; message: MessageDetail } | { kind: "missing" } | { kind: "unavailable" };

export async function fetchMessage(id: string): Promise<DetailResult> {
  const result = await adminFetch(`${MESSAGES}/${id}`, { method: "GET" });
  if (result.kind === "ok") return { kind: "found", message: result.data as MessageDetail };
  if (result.kind === "error" && (result.status === 404 || result.status === 422)) return { kind: "missing" };
  return { kind: "unavailable" };
}

/** Path-safe id check, shared by the detail page and the actions. */
export function isMessageId(value: unknown): value is string {
  return typeof value === "string" && /^[1-9]\d{0,18}$/.test(value);
}
