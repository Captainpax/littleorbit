"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useState } from "react";

interface Challenge {
  otpauth_uri: string;
  qr_svg_data_url: string;
}

interface EnrollmentStartPayload {
  password: string;
  current_totp_code?: string;
  current_recovery_code?: string;
}

export function buildEnrollmentStartPayload(form: FormData): EnrollmentStartPayload {
  const password = String(form.get("password") ?? "");
  const currentTotpCode = String(form.get("current_totp_code") ?? "").trim();
  const currentRecoveryCode = String(form.get("current_recovery_code") ?? "").trim();
  if (currentTotpCode && currentRecoveryCode) {
    throw new Error("Choose one current MFA proof.");
  }
  return {
    password,
    ...(currentTotpCode ? { current_totp_code: currentTotpCode } : {}),
    ...(currentRecoveryCode ? { current_recovery_code: currentRecoveryCode } : {}),
  };
}

export function AdminEnrollmentForm() {
  const [accessToken, setAccessToken] = useState("");
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [message, setMessage] = useState("");

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email"));
    let enrollmentPayload: EnrollmentStartPayload;
    try {
      enrollmentPayload = buildEnrollmentStartPayload(form);
    } catch {
      setMessage("Enter one current authenticator code or one recovery code, not both.");
      return;
    }
    const login = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password: enrollmentPayload.password }),
    });
    if (!login.ok) return setMessage("The owner credentials were not accepted.");
    const session = await login.json() as { access_token: string };
    const response = await fetch("/api/v1/admin/mfa/start", {
      method: "POST",
      headers: { Authorization: `Bearer ${session.access_token}`, "content-type": "application/json" },
      body: JSON.stringify(enrollmentPayload),
    });
    if (!response.ok) {
      return setMessage(response.status === 401
        ? "Replacing MFA requires one current authenticator or unused recovery code."
        : "This account cannot enroll owner MFA.");
    }
    setAccessToken(session.access_token);
    setChallenge(await response.json() as Challenge);
  }

  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/v1/admin/mfa/confirm", {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}`, "content-type": "application/json" },
      body: JSON.stringify({ code: form.get("code") }),
    });
    if (!response.ok) return setMessage("That code was not accepted. Wait for a fresh code and retry.");
    const result = await response.json() as { recovery_codes: string[] };
    setRecoveryCodes(result.recovery_codes);
    setChallenge(null);
    setAccessToken("");
  }

  if (recoveryCodes.length) {
    return <section className="account-form recovery-codes">
      <h1>Save these once</h1>
      <p>Each recovery code works once. Store them somewhere private; Little Orbit keeps only hashes.</p>
      <ul>{recoveryCodes.map((code) => <li key={code}><code>{code}</code></li>)}</ul>
      <Link className="button" href="/admin">Continue to console</Link>
    </section>;
  }

  if (challenge) {
    return <form className="account-form" onSubmit={confirm}>
      <h1>Scan and confirm</h1>
      <Image src={challenge.qr_svg_data_url} alt="Authenticator enrollment QR code" width={240} height={240} unoptimized />
      <details><summary>Manual setup URI</summary><code className="break-secret">{challenge.otpauth_uri}</code></details>
      <label>Current six-digit code<input name="code" inputMode="numeric" pattern="[0-9]{6}" autoComplete="one-time-code" required /></label>
      <p className="form-message" role="status">{message}</p>
      <button className="button">Enable MFA</button>
    </form>;
  }

  return <form className="account-form" onSubmit={start}>
    <span className="eyebrow">Owner enrollment</span><h1>Set up MFA</h1>
    <p>Enrollment requires a verified owner account and a fresh password check.</p>
    <label>Email<input name="email" type="email" autoComplete="username" required /></label>
    <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
    <p id="replacement-proof-help">For first setup, leave both fields blank. To replace enabled MFA, enter exactly one current proof.</p>
    <label>Current authenticator code<input name="current_totp_code" inputMode="numeric" pattern="[0-9]{6}" autoComplete="one-time-code" aria-describedby="replacement-proof-help" /></label>
    <label>Current recovery code<input name="current_recovery_code" minLength={13} maxLength={32} autoComplete="one-time-code" aria-describedby="replacement-proof-help" /></label>
    <p className="form-message" role="status">{message}</p>
    <button className="button">Continue securely</button>
  </form>;
}
