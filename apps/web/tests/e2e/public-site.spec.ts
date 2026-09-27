import { expect, test } from "@playwright/test";
import { currentRelease, hostedApkPath } from "../../src/lib/release";

test("landing page exposes mission and keyboard-visible actions", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Closer");
  await expect(page.getByRole("link", { name: /Download for Android/i })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
});

test("signup requires adult and terms attestations", async ({ page }) => {
  await page.goto("/signup");
  const honeypot = page.locator('input[name="website"]');
  await expect(honeypot).toBeHidden();
  await expect(honeypot).toHaveAttribute("readonly", "");
  await expect(honeypot).toHaveValue("");
  await page.getByLabel("Email").fill("browser-check@example.test");
  await page.getByLabel("Your name").fill("Browser Check");
  await page.getByLabel(/^Password/).fill("browser-test-password");
  await page.getByRole("button", { name: "Send verification email" }).click();
  await expect(page.getByLabel("I confirm I am 18 or older.")).toBeFocused();
  await expect(page.getByRole("status")).toHaveText("");
});

test("download remains available when release API metadata is unavailable", async ({ page }) => {
  await page.goto("/download");
  const download = page.getByRole("link", { name: "Download signed APK" });
  await expect(page.getByText("Available", { exact: true })).toBeVisible();
  await expect(page.getByText(currentRelease.sha256)).toBeVisible();
  await expect(download).toBeVisible();
  await expect(download).toHaveAttribute("href", hostedApkPath(currentRelease.version));
});

test("patch notes and RSS expose the same signed fallback release", async ({ request, page }) => {
  await page.goto("/patch-notes");
  await expect(page.getByRole("heading", { name: currentRelease.version })).toBeVisible();
  await expect(page.getByRole("link", { name: "Subscribe with RSS" }))
    .toHaveAttribute("href", "/patch-notes.xml");

  const response = await request.get("/patch-notes.xml");
  expect(response.ok()).toBe(true);
  expect(response.headers()["content-type"]).toContain("application/rss+xml");
  const xml = await response.text();
  expect(xml).toContain('<rss version="2.0">');
  expect(xml).toContain(currentRelease.version);
});

test("Wear handoff explains the phone-only installation path", async ({ page }) => {
  await page.goto("/app/install-wear");
  await expect(page.getByRole("heading", { name: "Continue on your phone" })).toBeVisible();
  await expect(page.getByText("No computer required")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open Little Orbit" }))
    .toHaveAttribute("href", "https://lil-orb.pax-kun.com/app/install-wear");
});

test("verification links fill their one-use token from the URL fragment", async ({ page }) => {
  const token = "a".repeat(43);
  await page.goto(`/verify-email#token=${token}`);
  await expect(page.getByLabel("Secure link token")).toHaveValue(token);
});

test("the public website does not expose an administrator panel", async ({ page }) => {
  const response = await page.goto("/admin");
  expect(response?.status()).toBe(404);
  await expect(page.getByLabel("Authenticator code")).toHaveCount(0);
});
