import { describe, expect, it } from "vitest";

import { buildEnrollmentStartPayload } from "./admin-enrollment-form";

function enrollmentForm(values: Record<string, string>): FormData {
  const form = new FormData();
  for (const [name, value] of Object.entries(values)) form.set(name, value);
  return form;
}

describe("administrator MFA enrollment payload", () => {
  it("keeps first enrollment password-only", () => {
    expect(buildEnrollmentStartPayload(enrollmentForm({ password: "secret" }))).toEqual({
      password: "secret",
    });
  });

  it("sends exactly one current proof for replacement", () => {
    expect(buildEnrollmentStartPayload(enrollmentForm({
      password: "secret",
      current_totp_code: " 123456 ",
    }))).toEqual({ password: "secret", current_totp_code: "123456" });
    expect(buildEnrollmentStartPayload(enrollmentForm({
      password: "secret",
      current_recovery_code: " abc123-def456 ",
    }))).toEqual({
      password: "secret",
      current_recovery_code: "abc123-def456",
    });
  });

  it("rejects ambiguous replacement proof", () => {
    expect(() => buildEnrollmentStartPayload(enrollmentForm({
      password: "secret",
      current_totp_code: "123456",
      current_recovery_code: "abc123-def456",
    }))).toThrow("Choose one current MFA proof.");
  });
});
