"use client";

import { useActionState } from "react";
import { login, type LoginState } from "@/app/admin/actions";

const INITIAL_STATE: LoginState = { error: null, email: "" };

export function LoginForm() {
  const [state, formAction, pending] = useActionState(login, INITIAL_STATE);
  return (
    <form className="admin-login-form" action={formAction}>
      {state.error && <p className="admin-alert" role="alert">{state.error}</p>}
      <label htmlFor="admin-email">Email</label>
      <input id="admin-email" name="email" type="email" autoComplete="username" required defaultValue={state.email} />
      <label htmlFor="admin-password">Password</label>
      <input id="admin-password" name="password" type="password" autoComplete="current-password" required />
      <button className="admin-button admin-button-primary" type="submit" disabled={pending}>
        {pending ? "Logging in…" : "Log in"}
      </button>
    </form>
  );
}
