import "server-only";

const TIMEOUT_MS = 5000;

export type BackendFieldError = { loc: string[]; type: string };

export type BackendResult =
  | { kind: "ok"; status: number; data: unknown }
  | { kind: "error"; status: number; code: string; fields: BackendFieldError[]; retryAfter: number | null }
  | { kind: "unavailable" };

type BackendRequest = {
  method: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
};

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

async function parseJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function toErrorResult(status: number, payload: unknown, retryHeader: string | null): BackendResult {
  const error = (payload as { error?: { code?: unknown; fields?: unknown } } | null)?.error;
  const retryAfter = retryHeader === null ? null : Number.parseInt(retryHeader, 10);
  return {
    kind: "error",
    status,
    code: typeof error?.code === "string" ? error.code : "unknown",
    fields: Array.isArray(error?.fields) ? (error.fields as BackendFieldError[]) : [],
    retryAfter: Number.isNaN(retryAfter) ? null : retryAfter,
  };
}

/** The only way Next.js talks to FastAPI. Never logs request bodies or headers. */
export async function backendFetch(path: string, request: BackendRequest): Promise<BackendResult> {
  try {
    const response = await fetch(`${requireEnv("BACKEND_URL")}${path}`, {
      method: request.method,
      headers: {
        "X-Internal-Token": requireEnv("BACKEND_INTERNAL_TOKEN"),
        ...(request.body === undefined ? {} : { "Content-Type": "application/json" }),
        ...request.headers,
      },
      body: request.body === undefined ? undefined : JSON.stringify(request.body),
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    const payload = await parseJson(response);
    if (response.ok) return { kind: "ok", status: response.status, data: payload };
    return toErrorResult(response.status, payload, response.headers.get("retry-after"));
  } catch (error) {
    console.error(`backend_unavailable path=${path} reason=${error instanceof Error ? error.name : "unknown"}`);
    return { kind: "unavailable" };
  }
}
