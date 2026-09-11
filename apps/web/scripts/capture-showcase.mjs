import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const baseUrl = process.env.SHOWCASE_BASE_URL ?? "http://127.0.0.1:8180";
const output = path.resolve(process.cwd(), "../../docs/assets");
await mkdir(output, { recursive: true });

const browser = await chromium.launch();

async function capture(name, route, viewport, mobile = false) {
  const context = await browser.newContext({ viewport, isMobile: mobile, colorScheme: "dark" });
  const page = await context.newPage();
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  const response = await page.goto(`${baseUrl}${route}`, { waitUntil: "networkidle" });
  if (!response?.ok()) throw new Error(`${route} returned ${response?.status()}`);
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.join(output, name), fullPage: true });
  if (errors.length) throw new Error(`${route} logged browser errors: ${errors.join("; ")}`);
  await context.close();
}

try {
  await capture("site-home-desktop.png", "/", { width: 1440, height: 1000 });
  await capture("site-home-mobile.png", "/", { width: 390, height: 844 }, true);
  await capture("site-signup.png", "/signup", { width: 1280, height: 900 });
  await capture("site-admin-login.png", "/admin/login", { width: 1280, height: 900 });
  console.log(`showcase screenshots saved to ${output}`);
} finally {
  await browser.close();
}
