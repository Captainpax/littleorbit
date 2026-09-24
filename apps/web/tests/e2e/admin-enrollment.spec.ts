import { expect, test } from "@playwright/test";

test("legacy owner enrollment is absent from the public website", async ({ page }) => {
  const response = await page.goto("/admin/enroll");

  expect(response?.status()).toBe(404);
  await expect(page.getByLabel("Current authenticator code")).toHaveCount(0);
  await expect(page.getByLabel("Current recovery code")).toHaveCount(0);
  await expect(page.getByLabel("Password")).toHaveCount(0);
});
