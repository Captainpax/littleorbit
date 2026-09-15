import { expect, test } from "@playwright/test";

test("owner MFA enrollment distinguishes first setup from replacement", async ({ page }) => {
  await page.goto("/admin/enroll");
  const authenticator = page.getByLabel("Current authenticator code");
  const recovery = page.getByLabel("Current recovery code");

  await expect(page.getByText("For first setup, leave both fields blank.")).toBeVisible();
  await expect(authenticator).not.toHaveAttribute("required", "");
  await expect(recovery).not.toHaveAttribute("required", "");

  await page.getByLabel("Email").fill("owner@example.test");
  await page.getByLabel("Password").fill("test-password-only");
  await authenticator.fill("123456");
  await recovery.fill("abc123-def456");
  await page.getByRole("button", { name: "Continue securely" }).click();

  await expect(page.getByRole("status"))
    .toHaveText("Enter one current authenticator code or one recovery code, not both.");
});
