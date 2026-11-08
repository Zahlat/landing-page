"use client";

import { useActionState } from "react";
import { submitContact } from "@/app/[lang]/contact/actions";
import type { ContactFormCopy } from "@/content/types";
import type { Locale } from "@/lib/i18n";
import {
  CONTACT_LIMITS,
  EMPTY_CONTACT_VALUES,
  MESSAGE_TYPES,
  type ContactField,
  type ContactFormState,
} from "@/lib/validation/contact-shared";

const INITIAL_STATE: ContactFormState = { status: "idle", values: EMPTY_CONTACT_VALUES, fieldErrors: {}, formError: null };

type Props = { locale: Locale; copy: ContactFormCopy; token: string };

export function ContactForm({ locale, copy, token }: Props) {
  const [state, formAction, pending] = useActionState(submitContact, INITIAL_STATE);

  const errorFor = (field: ContactField) => {
    const key = state.fieldErrors[field];
    return key ? copy.errors[key] : null;
  };
  const fieldProps = (field: ContactField) => ({
    id: `contact-${field}`,
    name: field,
    "aria-invalid": errorFor(field) ? true : undefined,
    "aria-describedby": errorFor(field) ? `contact-${field}-error` : undefined,
  });
  const fieldError = (field: ContactField) => {
    const message = errorFor(field);
    return message ? <p className="contact-field-error" id={`contact-${field}-error`}>{message}</p> : null;
  };

  return (
    <form className="contact-form" action={formAction} noValidate>
      <h2>{copy.heading}</h2>
      <p className="contact-form-intro">{copy.intro}</p>

      <input type="hidden" name="locale" value={locale} />
      <input type="hidden" name="formToken" value={token} />
      {/* Honeypot: invisible to people and skipped by keyboard. Bots tend to fill it in. */}
      <div className="contact-honeypot" aria-hidden="true">
        <label htmlFor="contact-website">{copy.honeypot}</label>
        <input id="contact-website" type="text" name="website" tabIndex={-1} autoComplete="off" />
      </div>

      <div className="contact-form-row">
        <div className="contact-field">
          <label htmlFor="contact-name">{copy.name}</label>
          <input {...fieldProps("name")} type="text" autoComplete="name" maxLength={CONTACT_LIMITS.nameMax} placeholder={copy.namePlaceholder} defaultValue={state.values.name} />
          {fieldError("name")}
        </div>
        <div className="contact-field">
          <label htmlFor="contact-email">{copy.email}</label>
          <input {...fieldProps("email")} type="email" dir="ltr" autoComplete="email" maxLength={CONTACT_LIMITS.emailMax} placeholder={copy.emailPlaceholder} defaultValue={state.values.email} />
          {fieldError("email")}
        </div>
      </div>

      <div className="contact-field">
        <label htmlFor="contact-type">{copy.type}</label>
        {/* Keyed so React restores the submitted choice after its post-action form reset. */}
        <select key={state.values.type} {...fieldProps("type")} defaultValue={state.values.type}>
          <option value="" disabled>{copy.typePlaceholder}</option>
          {MESSAGE_TYPES.map((type) => <option key={type} value={type}>{copy.types[type]}</option>)}
        </select>
        {fieldError("type")}
      </div>

      <div className="contact-field">
        <label htmlFor="contact-content">{copy.content}</label>
        <textarea {...fieldProps("content")} rows={6} placeholder={copy.contentPlaceholder} defaultValue={state.values.content} />
        {fieldError("content")}
      </div>

      {state.formError && <p className="contact-form-alert" role="alert">{copy.errors[state.formError]}</p>}
      {state.status === "success" && <p className="contact-form-success" role="status">{copy.success}</p>}

      <button className="button button-primary contact-form-submit" type="submit" disabled={pending}>
        {pending ? copy.sending : copy.submit}
      </button>
    </form>
  );
}
