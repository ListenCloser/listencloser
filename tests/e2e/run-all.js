/**
 * Comprehensive E2E test runner.
 * Tests each flow in isolation with proper cleanup.
 * Run with: node tests/e2e/run-all.js
 */

const { chromium } = require('playwright');

const BASE = 'https://hello-ai-wheat.vercel.app';
const WAIT = 10000;

async function testFlow(name, fn) {
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const result = await fn(browser);
    console.log(`${result ? '✅' : '❌'} ${name}`);
    return result;
  } catch (err) {
    console.log(`❌ ${name}: ${err.message.substring(0, 100)}`);
    return false;
  } finally {
    if (browser) await browser.close().catch(() => {});
  }
}

(async () => {
  const results = [];

  results.push(await testFlow('Chat sends message', async (browser) => {
    const page = await browser.newPage();
    await page.goto(`${BASE}/?tab=chat`);
    await page.waitForTimeout(WAIT);
    await page.locator('input[placeholder]').fill('hello');
    await page.locator('button[type=submit]').click();
    await page.waitForTimeout(15000);
    return await page.locator('[class*=assistant]').count() > 0;
  }));

  results.push(await testFlow('Chat follow-up', async (browser) => {
    const page = await browser.newPage();
    await page.goto(`${BASE}/?tab=chat`);
    await page.waitForTimeout(WAIT);
    await page.locator('input[placeholder]').fill('hello');
    await page.locator('button[type=submit]').click();
    await page.waitForTimeout(12000);
    await page.locator('input[placeholder]').fill('what can you do');
    await page.locator('button[type=submit]').click();
    await page.waitForTimeout(12000);
    return await page.locator('[class*=assistant]').count() >= 2;
  }));

  results.push(await testFlow('Chat history persists', async (browser) => {
    const page = await browser.newPage();
    await page.goto(`${BASE}/?tab=chat`);
    await page.waitForTimeout(WAIT);
    await page.locator('input[placeholder]').fill('hello');
    await page.locator('button[type=submit]').click();
    await page.waitForTimeout(12000);
    const b1 = await page.locator('[class*=assistant]').count();
    await page.goto(`${BASE}/?tab=library`);
    await page.waitForTimeout(5000);
    await page.goto(`${BASE}/?tab=chat`);
    await page.waitForTimeout(5000);
    return await page.locator('[class*=assistant]').count() >= b1;
  }));

  results.push(await testFlow('Library tab', async (browser) => {
    const page = await browser.newPage();
    await page.goto(`${BASE}/?tab=library`);
    await page.waitForTimeout(8000);
    return await page.locator('.drop-zone').isVisible();
  }));

  results.push(await testFlow('Transform tab', async (browser) => {
    const page = await browser.newPage();
    await page.goto(`${BASE}/?tab=transcribe`);
    await page.waitForTimeout(8000);
    return await page.locator('.source-grid').isVisible();
  }));

  results.push(await testFlow('Analyze tab', async (browser) => {
    const page = await browser.newPage();
    await page.goto(`${BASE}/?tab=analyze`);
    await page.waitForTimeout(8000);
    return await page.locator('.card').first().isVisible().catch(() => false);
  }));

  results.push(await testFlow('Visualize tab', async (browser) => {
    const page = await browser.newPage();
    await page.goto(`${BASE}/?tab=viz`);
    await page.waitForTimeout(8000);
    return await page.locator('.card').first().isVisible().catch(() => false);
  }));

  results.push(await testFlow('All tabs navigable', async (browser) => {
    const page = await browser.newPage();
    for (const tab of ['library', 'transcribe', 'viz', 'analyze', 'chat']) {
      await page.goto(`${BASE}/?tab=${tab}`);
      await page.waitForTimeout(3000);
    }
    return true;
  }));

  results.push(await testFlow('Chat attach button', async (browser) => {
    const page = await browser.newPage();
    await page.goto(`${BASE}/?tab=chat`);
    await page.waitForTimeout(8000);
    return await page.locator('input[type=file]').count() > 0;
  }));

  results.push(await testFlow('Sign-in button', async (browser) => {
    const page = await browser.newPage();
    await page.goto(BASE);
    await page.waitForTimeout(8000);
    return await page.locator('button').filter({ hasText: /sign/i }).count() > 0;
  }));

  const passed = results.filter(Boolean).length;
  console.log(`\n=== ${passed}/${results.length} tests passed ===`);
})();
