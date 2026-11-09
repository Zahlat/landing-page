import "server-only";
import { createHmac, timingSafeEqual } from "node:crypto";

const MIN_AGE_MS = 3_000;
const MAX_AGE_MS = 24 * 60 * 60 * 1000;
const TOKEN_PATTERN = /^(\d{1,16})\.([A-Za-z0-9_-]{43})$/;

export type FormTokenCheck = "ok" | "expired" | "rejected";

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

/** Replaces an expired token. Already past the minimum age: this visitor has waited long enough. */
export function signReplacementFormToken(now: number = Date.now()): string {
  return signFormToken(now - MIN_AGE_MS);
}

/**
 * "ok": authentic and between 3 seconds and 24 hours old.
 * "expired": authentic but over 24 hours old, so very likely a person with an old tab.
 * "rejected": forged, malformed or submitted faster than a person could.
 */
export function checkFormToken(token: string, now: number = Date.now()): FormTokenCheck {
  const match = TOKEN_PATTERN.exec(token);
  if (!match) return "rejected";
  const [, timestamp, supplied] = match;
  const suppliedBytes = Buffer.from(supplied, "base64url");
  const expected = signature(timestamp);
  if (suppliedBytes.length !== expected.length || !timingSafeEqual(suppliedBytes, expected)) return "rejected";
  const age = now - Number(timestamp);
  if (age < MIN_AGE_MS) return "rejected";
  return age > MAX_AGE_MS ? "expired" : "ok";
}
