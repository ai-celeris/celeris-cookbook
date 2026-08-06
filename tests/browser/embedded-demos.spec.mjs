import { expect, test } from "@playwright/test";

test("the hosted chatbot is fast, bounded, isolated, and renders replies as text", async ({ page }) => {
  await page.goto("/host/chatbot");
  const demo = page.frameLocator("#demo");
  const prompt = demo.locator("#prompt");
  await expect(prompt).toHaveAttribute("maxlength", "1000");

  for (let index = 0; index < 10; index += 1) {
    await prompt.fill(index === 0 ? '<img src=x onerror="window.__demoXss=true">' : `turn ${index}`);
    await demo.locator("#send").click();
    await expect(demo.locator("#send")).toBeEnabled();
  }

  await expect(demo.locator(".bubble.assistant").last()).toContainText("Fast reply <script>");
  expect(await demo.locator("body").evaluate(() => window.__demoXss)).toBeUndefined();
  const body = await page.request.get("/__last-chat").then((response) => response.json());
  expect(body.messages.length).toBeLessThanOrEqual(8);
  expect(Buffer.byteLength(JSON.stringify(body))).toBeLessThanOrEqual(7000);

  const iframe = page.locator("#demo");
  await expect.poll(() => iframe.evaluate((node) => node.style.height)).not.toBe("");
  const safeHeight = await iframe.evaluate((node) => node.style.height);
  await page.evaluate(() => window.postMessage({ type: "celeris-demo-height", height: 1199 }, location.origin));
  await expect(iframe).toHaveCSS("height", safeHeight);

  await page.locator("#theme").click();
  await expect(demo.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("instant suggest calls the shared route and tests the safe result locally", async ({ page }) => {
  await page.goto("/host/instant-suggest");
  const demo = page.frameLocator("#demo");
  const description = demo.locator("#description");
  await expect(description).toHaveAttribute("maxlength", "500");
  await description.fill("the exact word hello");
  await expect(demo.locator("#regex")).toHaveText("^hello$");
  await expect(demo.locator("#test-results li").first()).toBeVisible();
});
