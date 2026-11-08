"use server";

import { revalidatePath } from "next/cache";
import { redirect, RedirectType } from "next/navigation";
import { z } from "zod";
import { isMessageStatus, isMessageType, type LoadMoreResult } from "@/lib/admin-types";
import { fetchMessagePage, isMessageId } from "@/lib/server/admin-api";
import { adminFetch, clearSessionCookie, revokeCurrentSession, setSessionCookie } from "@/lib/server/admin-session";
import { backendFetch } from "@/lib/server/backend";
import { clientInfoHeaders, getClientInfo } from "@/lib/server/client-info";

export type LoginState = { error: string | null; email: string };

const LIST_PATH = "/admin/messages";
const API_PATH = "/v1/admin/messages";
const INVALID_LOGIN = "Invalid email or password.";

const loginSchema = z.object({
  email: z.string().trim().min(3).max(254),
  password: z.string().min(1).max(1024),
});
const loginResponseSchema = z.object({ token: z.string(), expires_at: z.string() });

function field(formData: FormData, key: string): string {
  const value = formData.get(key);
  return typeof value === "string" ? value : "";
}

/** The only action that runs without a session, because it is what creates one. */
export async function login(_previous: LoginState, formData: FormData): Promise<LoginState> {
  const email = field(formData, "email");
  const parsed = loginSchema.safeParse({ email, password: field(formData, "password") });
  if (!parsed.success) return { error: INVALID_LOGIN, email };

  const result = await backendFetch("/v1/admin/auth/login", {
    method: "POST",
    body: parsed.data,
    headers: clientInfoHeaders(await getClientInfo()),
  });
  if (result.kind === "unavailable") return { error: "The service is unavailable. Please try again shortly.", email };
  if (result.kind === "error") {
    if (result.status === 429) return { error: "Too many attempts. Please try again later.", email };
    if (result.status === 401 || result.status === 422) return { error: INVALID_LOGIN, email };
    return { error: "Sign-in failed. Please try again shortly.", email };
  }

  const session = loginResponseSchema.safeParse(result.data);
  if (!session.success) return { error: "Sign-in failed. Please try again shortly.", email };
  await setSessionCookie(session.data.token, session.data.expires_at);
  redirect(LIST_PATH);
}

export async function logout(): Promise<void> {
  await revokeCurrentSession();
  await clearSessionCookie();
  redirect("/admin/login");
}

export async function updateStatus(formData: FormData): Promise<void> {
  const id = field(formData, "id");
  const status = field(formData, "status");
  if (!isMessageId(id) || !isMessageStatus(status)) redirect(LIST_PATH);

  const result = await adminFetch(`${API_PATH}/${id}`, { method: "PATCH", body: { status } });
  if (result.kind === "error" && result.status === 404) redirect(LIST_PATH);
  if (result.kind !== "ok") redirect(`${LIST_PATH}/${id}?error=1`, RedirectType.replace);
  revalidatePath("/admin", "layout");
  redirect(`${LIST_PATH}/${id}`, RedirectType.replace);
}

export async function deleteMessage(formData: FormData): Promise<void> {
  const id = field(formData, "id");
  if (!isMessageId(id)) redirect(LIST_PATH);

  const result = await adminFetch(`${API_PATH}/${id}`, { method: "DELETE" });
  const gone = result.kind === "ok" || (result.kind === "error" && result.status === 404);
  if (!gone) redirect(`${LIST_PATH}/${id}?error=1`, RedirectType.replace);
  revalidatePath("/admin", "layout");
  redirect(LIST_PATH);
}

export async function loadMoreMessages(input: { status: unknown; type: unknown; cursor: unknown }): Promise<LoadMoreResult> {
  const { status, type, cursor } = input;
  if (typeof cursor !== "string" || cursor.length === 0 || cursor.length > 200) return { ok: false };
  if (status !== null && !isMessageStatus(status)) return { ok: false };
  if (type !== null && !isMessageType(type)) return { ok: false };
  const page = await fetchMessagePage({ status, type }, cursor);
  return page ? { ok: true, ...page } : { ok: false };
}
