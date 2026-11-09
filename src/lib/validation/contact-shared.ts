import type { ContactFormErrors } from "@/content/types";

// Imported by the client form, so this file must stay free of Zod (see contact.ts).

export const MESSAGE_TYPES = ["suggestion", "request", "question", "other"] as const;

/** Same limits as Pydantic. FastAPI remains the authority. */
export const CONTACT_LIMITS = { nameMax: 100, emailMax: 254, contentMin: 10, contentMax: 5000 } as const;

export type ContactErrorKey = keyof ContactFormErrors;
export type ContactField = "name" | "email" | "type" | "content";
export type ContactFormValues = Record<ContactField, string>;

export type ContactFormState = {
  status: "idle" | "success" | "error";
  values: ContactFormValues;
  fieldErrors: Partial<Record<ContactField, ContactErrorKey>>;
  formError: ContactErrorKey | null;
  /** Replaces the page's token once the original has expired. */
  freshToken: string | null;
};

export const EMPTY_CONTACT_VALUES: ContactFormValues = { name: "", email: "", type: "", content: "" };
