"use server";

import { backendFetch, type BackendFieldError } from "@/lib/server/backend";
import { clientInfoHeaders, getClientInfo } from "@/lib/server/client-info";
import { checkFormToken, signReplacementFormToken } from "@/lib/server/form-token";
import { contactSchema } from "@/lib/validation/contact";
import {
  EMPTY_CONTACT_VALUES,
  type ContactErrorKey,
  type ContactField,
  type ContactFormState,
  type ContactFormValues,
} from "@/lib/validation/contact-shared";

// Bots get exactly what a real sender gets, so they can't learn they were filtered.
const SUCCESS: ContactFormState = { status: "success", values: EMPTY_CONTACT_VALUES, fieldErrors: {}, formError: null, freshToken: null };

function text(formData: FormData, key: string): string {
  const value = formData.get(key);
  return typeof value === "string" ? value : "";
}

function isContactField(value: unknown): value is ContactField {
  return value === "name" || value === "email" || value === "type" || value === "content";
}

function errorKeyForBackendField(field: ContactField, errorType: string): ContactErrorKey {
  switch (field) {
    case "name": return errorType === "string_too_long" ? "nameTooLong" : "nameRequired";
    case "email": return "emailInvalid";
    case "type": return "typeRequired";
    case "content": return errorType === "string_too_long" ? "contentTooLong" : "contentTooShort";
  }
}

function backendFieldErrors(fields: BackendFieldError[]): ContactFormState["fieldErrors"] {
  const errors: ContactFormState["fieldErrors"] = {};
  for (const { loc, type } of fields) {
    const field = loc.at(-1);
    if (isContactField(field) && !errors[field]) errors[field] = errorKeyForBackendField(field, type);
  }
  return errors;
}

export async function submitContact(previous: ContactFormState, formData: FormData): Promise<ContactFormState> {
  const freshToken = previous.freshToken;
  const success: ContactFormState = { ...SUCCESS, freshToken };
  if (text(formData, "website") !== "") return success;
  const tokenCheck = checkFormToken(text(formData, "formToken"));
  if (tokenCheck === "rejected") return success;

  const values: ContactFormValues = {
    name: text(formData, "name"),
    email: text(formData, "email"),
    type: text(formData, "type"),
    content: text(formData, "content"),
  };
  // An authentic but old token is a person with a long-open tab, so tell them instead of
  // silently dropping their message. A reload would erase their text, so hand over a new token.
  if (tokenCheck === "expired") {
    return { status: "error", values, fieldErrors: {}, formError: "formExpired", freshToken: signReplacementFormToken() };
  }
  const failure = (fieldErrors: ContactFormState["fieldErrors"], formError: ContactErrorKey | null): ContactFormState =>
    ({ status: "error", values, fieldErrors, formError, freshToken });

  const parsed = contactSchema.safeParse({ ...values, locale: text(formData, "locale") });
  if (!parsed.success) {
    const fieldErrors: ContactFormState["fieldErrors"] = {};
    for (const issue of parsed.error.issues) {
      const field = issue.path[0];
      if (isContactField(field) && !fieldErrors[field]) fieldErrors[field] = issue.message as ContactErrorKey;
    }
    // Only a tampered locale fails without a visible field to attach the error to.
    return failure(fieldErrors, Object.keys(fieldErrors).length === 0 ? "server" : null);
  }

  const result = await backendFetch("/v1/messages", {
    method: "POST",
    body: parsed.data,
    headers: clientInfoHeaders(await getClientInfo()),
  });
  if (result.kind === "ok") return success;
  if (result.kind === "error") {
    if (result.code === "rate_limited") return failure({}, "rateLimited");
    if (result.code === "too_many_links") return failure({ content: "tooManyLinks" }, null);
    // FastAPI caps bodies at 16 KB, which emoji-heavy text can pass within 5000 characters.
    if (result.status === 413) return failure({ content: "contentTooLong" }, null);
    if (result.code === "validation_error") {
      const fieldErrors = backendFieldErrors(result.fields);
      if (Object.keys(fieldErrors).length > 0) return failure(fieldErrors, null);
    }
    console.error(`contact_submit_failed status=${result.status} code=${result.code}`);
  }
  return failure({}, "server");
}
