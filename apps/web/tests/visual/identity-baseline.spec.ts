import { expect, test } from "@playwright/test";

// Identity review needs a fixed small-size proof independent of whichever
// landing composition happens to be current. Keep this as a local review
// artifact rather than another hosted Argos snapshot: the favicon itself is
// the subject, not a pixel-regression gate.
test("identity — favicon scale sheet", async ({ page }) => {
  await page.setViewportSize({ width: 420, height: 240 });
  await page.goto("/");

  await page.evaluate(() => {
    document.body.innerHTML = `
      <main
        data-testid="identity-scale-sheet"
        style="
          min-height: 100vh;
          display: grid;
          place-items: center;
          margin: 0;
          background: #f5f5f3;
          color: #1a1a1a;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        "
      >
        <section style="display: flex; align-items: end; gap: 32px; padding: 32px;">
          ${[64, 32, 16].map((size) => `
            <figure style="display: grid; justify-items: center; gap: 10px; margin: 0;">
              <img
                src="/icon.svg"
                width="${size}"
                height="${size}"
                alt="Listen Closer favicon at ${size} pixels"
                style="display: block; width: ${size}px; height: ${size}px;"
              />
              <figcaption style="font-size: 11px; line-height: 1; color: #6b6b6b;">
                ${size}px
              </figcaption>
            </figure>
          `).join("")}
        </section>
      </main>
    `;
  });

  await page.waitForFunction(() => Array.from(document.images).every((image) => image.complete));
  const sheet = page.getByTestId("identity-scale-sheet");
  await expect(sheet).toBeVisible();
  await sheet.screenshot({ path: "screenshots/app-identity-scale.png" });
});
