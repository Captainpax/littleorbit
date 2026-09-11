"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

interface AccountFormProps { mode: "signup" | "forgot" | "verify" | "reset" | "resend"; }

const copy = {
  signup: { title: "Create your account", action: "/api/v1/auth/register", submit: "Send verification email" },
  forgot: { title: "Recover your account", action: "/api/v1/auth/forgot-password", submit: "Send recovery email" },
  verify: { title: "Verify your email", action: "/api/v1/auth/verify", submit: "Verify email" },
  reset: { title: "Choose a new password", action: "/api/v1/auth/reset-password", submit: "Update password" },
  resend: { title: "Need a new link?", action: "/api/v1/auth/resend-verification", submit: "Resend verification email" },
} as const;

export function AccountForm({ mode }: Readonly<AccountFormProps>) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const linkTokenRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (mode !== "verify" && mode !== "reset") return;
    const fragmentToken = new URLSearchParams(window.location.hash.slice(1)).get("token");
    const legacyQueryToken = new URLSearchParams(window.location.search).get("token");
    if (linkTokenRef.current) {
      linkTokenRef.current.value = fragmentToken ?? legacyQueryToken ?? "";
    }
  }, [mode]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage("");
    const data: Record<string, unknown> = Object.fromEntries(new FormData(event.currentTarget));
    if (mode === "signup") {
      delete data.adult_confirmed;
      delete data.terms_confirmed;
      data.is_adult = true;
      data.accepted_terms_version = "2026-09-10";
    }
    try {
      const response = await fetch(copy[mode].action, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(data) });
      const result = await response.json() as { message?: string; detail?: string };
      setMessage(result.message ?? result.detail ?? "That request could not be completed.");
      if (mode === "verify" && response.ok) {
        router.push("/app/sign-in");
      }
    } catch { setMessage("Little Orbit could not reach the server. Your form was not submitted."); }
    finally { setBusy(false); }
  }

  return (
    <form className="account-form" onSubmit={submit}>
      <h2>{copy[mode].title}</h2>
      {(mode === "signup" || mode === "forgot" || mode === "resend") && (
        <label>Email<input name="email" type="email" autoComplete="email" required /></label>
      )}
      {mode === "signup" && (
        <label>Your name<input name="display_name" autoComplete="name" minLength={1} maxLength={80} required /></label>
      )}
      {(mode === "signup" || mode === "reset") && (
        <label>
          {mode === "reset" ? "New password" : "Password"}
          <input name="password" type="password" autoComplete="new-password" minLength={12} required />
          <small>At least 12 characters</small>
        </label>
      )}
      {(mode === "verify" || mode === "reset") && (
        <label>
          Secure link token
          <input
            name="token"
            ref={linkTokenRef}
            autoComplete="one-time-code"
            minLength={32}
            required
          />
        </label>
      )}
      {mode === "signup" && (
        <>
          <label className="check">
            <input name="adult_confirmed" type="checkbox" required />
            <span>I confirm I am 18 or older.</span>
          </label>
          <label className="check">
            <input name="terms_confirmed" type="checkbox" required />
            <span>I accept the privacy notice and terms.</span>
          </label>
          {/* A controlled read-only field keeps mobile autofill from tripping the bot honeypot. */}
          <label className="honeypot" aria-hidden="true" hidden>
            Leave this field blank
            <input
              name="website"
              type="text"
              value=""
              readOnly
              tabIndex={-1}
              autoComplete="off"
              data-1p-ignore="true"
              data-lpignore="true"
            />
          </label>
        </>
      )}
      <button className="button" disabled={busy}>{busy ? "Working…" : copy[mode].submit}</button>
      <p className="form-message" role="status" aria-live="polite">{message}</p>
    </form>
  );
}
