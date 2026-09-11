import { expect, test } from "@playwright/test";

test("landing page exposes mission and keyboard-visible actions", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Closer");
  await expect(page.getByRole("link", { name: /Download for Android/i })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
});

test("signup requires adult and terms attestations", async ({ page }) => {
  await page.goto("/signup");
  await page.getByLabel("Email").fill("browser-check@example.test");
  await page.getByLabel("Your name").fill("Browser Check");
  await page.getByLabel(/^Password/).fill("browser-test-password");
  await page.getByRole("button", { name: "Send verification email" }).click();
  await expect(page.getByLabel("I confirm I am 18 or older.")).toBeFocused();
  await expect(page.getByRole("status")).toHaveText("");
});

test("verification links fill their one-use token from the URL fragment", async ({ page }) => {
  const token = "a".repeat(43);
  await page.goto(`/verify-email#token=${token}`);
  await expect(page.getByLabel("Secure link token")).toHaveValue(token);
});

test("admin redirects to password and second-factor entry", async ({ page }) => {
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/admin\/login/);
  await expect(page.getByLabel("Authenticator code")).toBeVisible();
  await expect(page.getByLabel("Recovery code")).toBeVisible();
});

test("a forged admin cookie is rejected by the server", async ({ context, page, baseURL }) => {
  await context.addCookies([{
    name: "little_orbit_admin",
    value: "forged",
    url: `${baseURL}/admin`,
  }]);
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/admin\/login/);
});
