"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const versionPattern = /^[0-9A-Za-z._-]{1,40}$/;

async function adminMutation(path: string, method: "POST" | "PUT" | "PATCH", body: unknown) {
  const token = (await cookies()).get("little_orbit_admin")?.value;
  if (!token) redirect("/admin/login");
  const baseUrl = process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000";
  const response = await fetch(`${baseUrl}/v1/admin/${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (response.status === 401 || response.status === 403) redirect("/admin/login");
  if (!response.ok) throw new Error(`Owner action failed with status ${response.status}`);
  revalidatePath("/admin");
}

function required(formData: FormData, name: string): string {
  const value = formData.get(name);
  if (typeof value !== "string" || !value) throw new Error(`Missing ${name}`);
  return value;
}

function optional(formData: FormData, name: string): string | null {
  const value = formData.get(name);
  return typeof value === "string" && value ? value : null;
}

/** Pause or resume public registration through the audited API. */
export async function setRegistration(formData: FormData) {
  await adminMutation("registration", "PUT", { enabled: required(formData, "enabled") === "true" });
}

/** Resolve a question report, optionally disabling the source question globally. */
export async function resolveReport(formData: FormData) {
  const reportId = required(formData, "report_id");
  if (!uuidPattern.test(reportId)) throw new Error("Invalid report identifier");
  await adminMutation(`question-reports/${reportId}/resolve`, "POST", {
    disable_question: formData.get("disable_question") === "on",
  });
}

/** Queue a future unanswered question pool for fresh generation. */
export async function regenerateBatch(formData: FormData) {
  const publishDate = required(formData, "publish_date");
  if (!datePattern.test(publishDate)) throw new Error("Invalid publication date");
  await adminMutation(`question-batches/${publishDate}/regenerate`, "POST", {});
}

/** Suspend or restore one non-owner account. */
export async function updateAccount(formData: FormData) {
  const accountId = required(formData, "account_id");
  if (!uuidPattern.test(accountId)) throw new Error("Invalid account identifier");
  await adminMutation(`accounts/${accountId}`, "PATCH", {
    suspended: required(formData, "suspended") === "true",
  });
}

/** Revoke all sessions for an account without exposing any session token. */
export async function revokeSessions(formData: FormData) {
  const accountId = required(formData, "account_id");
  if (!uuidPattern.test(accountId)) throw new Error("Invalid account identifier");
  await adminMutation(`accounts/${accountId}/revoke-sessions`, "POST", {});
}

/** Atomically replace the validated curated question bank from JSON. */
export async function replaceCuratedBank(formData: FormData) {
  const questions = JSON.parse(required(formData, "questions")) as unknown;
  if (!Array.isArray(questions)) throw new Error("Question bank must be an array");
  await adminMutation("curated-bank", "PUT", { questions });
}

/** Publish signed APK metadata used by first-party delivery and the download page. */
export async function publishRelease(formData: FormData) {
  const version = required(formData, "version");
  const requiredAfter = optional(formData, "required_after");
  if (!versionPattern.test(version)) throw new Error("Invalid release version");
  await adminMutation(`releases/${encodeURIComponent(version)}`, "PUT", {
    version,
    version_code: Number(required(formData, "version_code")),
    apk_url: required(formData, "apk_url"),
    github_release_url: required(formData, "github_release_url"),
    sha256: required(formData, "sha256"),
    size_bytes: Number(required(formData, "size_bytes")),
    package_name: required(formData, "package_name"),
    signer_sha256: required(formData, "signer_sha256"),
    minimum_android: Number(required(formData, "minimum_android")),
    minimum_supported_version_code: Number(required(formData, "minimum_supported_version_code")),
    required_after: requiredAfter ? new Date(requiredAfter).toISOString() : null,
    release_notes: required(formData, "release_notes"),
    publish: formData.get("publish") === "on",
  });
}
