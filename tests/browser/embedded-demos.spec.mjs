import { expect, test } from "@playwright/test";

test("the chatbot is fast, bounded, isolated, and renders replies as text", async ({ page }) => {
  await page.goto("/apps/chatbot/");
  const prompt = page.locator("#prompt");
  await expect(prompt).toHaveAttribute("maxlength", "1000");

  for (let index = 0; index < 10; index += 1) {
    await prompt.fill(index === 0 ? '<img src=x onerror="window.__demoXss=true">' : `turn ${index}`);
    await page.locator("#send").click();
    await expect(page.locator("#send")).toBeEnabled();
  }

  await expect(page.locator(".bubble.assistant").last()).toContainText("Fast reply <script>");
  expect(await page.locator("body").evaluate(() => window.__demoXss)).toBeUndefined();
  const body = await page.request.get("/__last-chat").then((response) => response.json());
  expect(body.messages.length).toBeLessThanOrEqual(8);
  expect(Buffer.byteLength(JSON.stringify(body))).toBeLessThanOrEqual(7000);
});

test("instant suggest calls its API and tests the safe result locally", async ({ page }) => {
  await page.goto("/apps/instant-suggest/");
  const description = page.locator("#description");
  await expect(description).toHaveAttribute("maxlength", "500");
  await description.fill("the exact word hello");
  await expect(page.locator("#regex")).toHaveText("^hello$");
  await expect(page.locator("#test-results li").first()).toBeVisible();
});

test("instant search makes query understanding visible", async ({ page }) => {
  await page.goto("/apps/instant-search/");
  const query = page.locator("#query");
  await expect(query).toHaveAttribute("maxlength", "500");
  await query.fill("why am I told to slow down");
  await expect(page.locator("#keywords")).toContainText("rate limiting");
  await expect(page.locator("#understood-results")).toContainText("Rate limits and 429 responses");
  await expect(page.locator("#latency")).toHaveText("14 ms model time");
});
