import "server-only";
import { createHmac, timingSafeEqual } from "node:crypto";

const MIN_AGE_MS = 3_000;
const MAX_AGE_MS = 24 * 60 * 60 * 1000;
const TOKEN_PATTERN = /^(\d{1,16})\.([A-Za-z0-9_-]{43})$/;

function signature(timestamp: string): Buffer {
  const secret = process.env.FORM_SIGNING_SECRET;
  if (!secret) throw new Error("FORM_SIGNING_SECRET is not set");
  return createHmac("sha256", secret).update(`contact-form:${timestamp}`).digest();
}

/** Signed render time. The page must be rendered per request for this to mean anything. */
export function signFormToken(now: number = Date.now()): string {
  const timestamp = String(now);
  return `${timestamp}.${signature(timestamp).toString("base64url")}`;
}

/** True only for an authentic token issued between 3 seconds and 24 hours ago. */
export function verifyFormToken(token: string, now: number = Date.now()): boolean {
  const match = TOKEN_PATTERN.exec(token);
  if (!match) return false;
  const [, timestamp, supplied] = match;
  const suppliedBytes = Buffer.from(supplied, "base64url");
  const expected = signature(timestamp);
  if (suppliedBytes.length !== expected.length || !timingSafeEqual(suppliedBytes, expected)) return false;
  const age = now - Number(timestamp);
  return age >= MIN_AGE_MS && age <= MAX_AGE_MS;
}
