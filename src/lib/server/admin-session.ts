import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";
import { backendFetch, type BackendResult } from "@/lib/server/backend";

const LOGIN_PATH = "/admin/login";
const isProduction = process.env.NODE_ENV === "production";

// __Host- makes browsers refuse the cookie unless it is Secure, has no Domain and has Path=/.
// It can't be set over plain http://, so local development uses the unprefixed name.
const COOKIE_NAME = isProduction ? "__Host-meraki_admin" : "meraki_admin";
const COOKIE_OPTIONS = { httpOnly: true, secure: isProduction, sameSite: "strict", path: "/" } as const;

export type Admin = { email: string };

const bearer = (token: string) => ({ Authorization: `Bearer ${token}` });

async function readToken(): Promise<string | null> {
  return (await cookies()).get(COOKIE_NAME)?.value || null;
}

/** Server Actions only: cookies can't be written while a page renders. */
export async function setSessionCookie(token: string, expiresAt: string): Promise<void> {
  const maxAge = Math.max(0, Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000));
  (await cookies()).set(COOKIE_NAME, token, { ...COOKIE_OPTIONS, maxAge });
}

/** Sets maxAge=0 with the original options; browsers ignore a __Host- removal without Secure. */
export async function clearSessionCookie(): Promise<void> {
  (await cookies()).set(COOKIE_NAME, "", { ...COOKIE_OPTIONS, maxAge: 0 });
}

/** The signed-in admin, or null. Cached so a layout and page share one lookup per request. */
export const getAdmin = cache(async (): Promise<Admin | null> => {
  const token = await readToken();
  if (!token) return null;
  const result = await backendFetch("/v1/admin/me", { method: "GET", headers: bearer(token) });
  return result.kind === "ok" ? (result.data as Admin) : null;
});

export async function requireAdmin(): Promise<Admin> {
  return (await getAdmin()) ?? redirect(LOGIN_PATH);
}

/**
 * Backend call as the signed-in admin. FastAPI validates the session on every call, so each
 * page fetch and Server Action is authorized here, not just by the layout. A missing or
 * rejected session redirects to the login page instead of returning.
 */
export async function adminFetch(
  path: string,
  request: { method: "GET" | "PATCH" | "DELETE"; body?: unknown },
): Promise<BackendResult> {
  const token = await readToken();
  if (!token) redirect(LOGIN_PATH);
  const result = await backendFetch(path, { ...request, headers: bearer(token) });
  if (result.kind === "error" && result.status === 401) redirect(LOGIN_PATH);
  return result;
}

/** Revokes the current session server-side, whatever state the backend reports it in. */
export async function revokeCurrentSession(): Promise<void> {
  const token = await readToken();
  if (token) await backendFetch("/v1/admin/auth/logout", { method: "POST", headers: bearer(token) });
}
