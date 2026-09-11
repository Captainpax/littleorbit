"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

type LoginState = "idle" | "submitting" | "error";

export function AdminLoginForm() {
  const router = useRouter();
  const [state, setState] = useState<LoginState>("idle");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("submitting");
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/v1/admin/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: form.get("email"),
        password: form.get("password"),
        totp_code: form.get("totp_code") || null,
        recovery_code: form.get("recovery_code") || null,
      }),
    });
    if (!response.ok) {
      setState("error");
      return;
    }
    router.push("/admin");
  }

  return (
    <form className="account-form" onSubmit={submit}>
      <span className="eyebrow">Owner console</span>
      <h1>Protected operations</h1>
      <p>Password and a current authenticator code are required. Relationship content is unavailable here.</p>
      <label>Email<input name="email" type="email" autoComplete="username" required /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
      <label>Authenticator code<input name="totp_code" inputMode="numeric" pattern="[0-9]{6}" autoComplete="one-time-code" /></label>
      <label>Recovery code<input name="recovery_code" minLength={13} maxLength={32} autoComplete="one-time-code" /></label>
      <small>Enter one authenticator code or one unused recovery code.</small>
      {state === "error" ? <p className="form-message error" role="alert">Those administrator credentials were not accepted.</p> : null}
      <button className="button" disabled={state === "submitting"}>
        {state === "submitting" ? "Checking…" : "Sign in securely"}
      </button>
      <Link href="/admin/enroll">Set up owner MFA</Link>
    </form>
  );
}
