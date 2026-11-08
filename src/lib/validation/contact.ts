import { z } from "zod";
import { locales } from "@/lib/i18n";
import { CONTACT_LIMITS, MESSAGE_TYPES } from "@/lib/validation/contact-shared";

// Python counts code points; JS .length counts UTF-16 units, which differ for emoji.
const charCount = (value: string) => Array.from(value).length;

/** Every error message is a ContactErrorKey, translated in the form component. */
export const contactSchema = z.object({
  name: z.string().trim()
    .refine((value) => charCount(value) >= 1, "nameRequired")
    .refine((value) => charCount(value) <= CONTACT_LIMITS.nameMax, "nameTooLong"),
  email: z.string().trim().pipe(
    z.email({ pattern: z.regexes.unicodeEmail, error: "emailInvalid" }).max(CONTACT_LIMITS.emailMax, "emailInvalid"),
  ),
  type: z.enum(MESSAGE_TYPES, { error: "typeRequired" }),
  content: z.string().trim()
    .refine((value) => charCount(value) >= CONTACT_LIMITS.contentMin, "contentTooShort")
    .refine((value) => charCount(value) <= CONTACT_LIMITS.contentMax, "contentTooLong"),
  locale: z.enum(locales),
});
