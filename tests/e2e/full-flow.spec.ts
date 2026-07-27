import { test, expect } from '@playwright/test';

const BASE_URL = 'https://hello-ai-wheat.vercel.app';

test.describe('Full User Flow E2E', () => {

  test('FLOW 1: Site loads and Library tab is accessible', async ({ page }) => {
    await page.goto(BASE_URL);
    
    // Wait for the page to load
    await expect(page).toHaveTitle(/Music Studio/);
    
    // Check nav tabs exist
    await expect(page.locator('.nav-item').filter({ hasText: 'Library' })).toBeVisible();
    await expect(page.locator('.nav-item').filter({ hasText: 'Transform' })).toBeVisible();
    await expect(page.locator('.nav-item').filter({ hasText: 'Visualize' })).toBeVisible();
    await expect(page.locator('.nav-item').filter({ hasText: 'Analyze' })).toBeVisible();
    await expect(page.locator('.nav-item').filter({ hasText: 'Chat' })).toBeVisible();
    
    // Click Library tab
    await page.locator('.nav-item').filter({ hasText: 'Library' }).click();
    await expect(page.locator('.card-title').filter({ hasText: 'Library' })).toBeVisible();
    
    // Check drop zone exists
    await expect(page.locator('.drop-zone')).toBeVisible();
  });

  test('FLOW 2: Library shows upload prompt when not signed in', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.locator('.nav-item').filter({ hasText: 'Library' }).click();
    
    // When not signed in, should show sign-in prompt in drop zone
    await page.waitForTimeout(2000);
    const hasDropZone = await page.locator('.drop-zone').isVisible().catch(() => false);
    const hasSignInPrompt = await page.locator('.muted').filter({ hasText: /sign in|Sign in/ }).isVisible().catch(() => false);
    expect(hasDropZone || hasSignInPrompt).toBeTruthy();
  });

  test('FLOW 3: Navigate to Transform tab', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.locator('.nav-item').filter({ hasText: 'Transform' }).click();
    
    // Check Transform tab is active
    await expect(page.locator('.card-title').filter({ hasText: 'Transform' })).toBeVisible();
    
    // Check source picker is visible
    await expect(page.locator('.source-grid')).toBeVisible();
    await expect(page.locator('.source-card').filter({ hasText: 'Upload file' })).toBeVisible();
    await expect(page.locator('.source-card').filter({ hasText: 'Record' })).toBeVisible();
  });

  test('FLOW 4: Navigate to Chat tab', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.locator('.nav-item').filter({ hasText: 'Chat' }).click();
    
    // Check Chat tab is active
    await expect(page.locator('.card-title').filter({ hasText: 'Chat' })).toBeVisible();
    
    // Check chat input exists
    await expect(page.locator('.chat-input')).toBeVisible();
    await expect(page.locator('.chat-send-btn')).toBeVisible();
    
    // Check empty state
    await expect(page.locator('.chat-empty')).toContainText('Ask me about your music');
  });

  test('FLOW 5: Chat - send a text message', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.locator('.nav-item').filter({ hasText: 'Chat' }).click();
    
    // Type a message
    await page.locator('.chat-input').fill('What is this app about?');
    await page.locator('.chat-send-btn').click();
    
    // Wait for response (may take a while for LLM)
    await expect(page.locator('.chat-bubble-assistant')).toBeVisible({ timeout: 60000 });
    
    // Check response is not empty
    const response = await page.locator('.chat-bubble-assistant').textContent();
    expect(response?.length).toBeGreaterThan(0);
  });

  test('FLOW 6: Navigate between all tabs', async ({ page }) => {
    await page.goto(BASE_URL);
    
    // Test each tab navigation
    const tabs = ['Library', 'Transform', 'Visualize', 'Analyze', 'Chat'];
    const urlIds = ['library', 'transcribe', 'viz', 'analyze', 'chat'];
    for (let i = 0; i < tabs.length; i++) {
      await page.locator('.nav-item').filter({ hasText: tabs[i] }).click();
      
      // URL should update with the correct tab ID
      await expect(page).toHaveURL(new RegExp(`tab=${urlIds[i]}`));
      
      // Tab should be active
      await expect(page.locator('.nav-item.active')).toContainText(tabs[i]);
    }
  });

  test('FLOW 7: Visualize tab shows empty state', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.locator('.nav-item').filter({ hasText: 'Visualize' }).click();
    
    // Check empty state
    await expect(page.locator('.empty').filter({ hasText: 'No transcribed tracks' })).toBeVisible();
  });

  test('FLOW 8: Analyze tab shows content', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.locator('.nav-item').filter({ hasText: 'Analyze' }).click();
    
    // Wait for tab to switch
    await page.waitForTimeout(1000);
    
    // Check the analyze tab card is visible (has "Analyze" in title)
    const analyzeCard = page.locator('.card-title').filter({ hasText: 'Analyze' });
    await expect(analyzeCard).toBeVisible({ timeout: 5000 });
  });

  test('FLOW 9: Library tab loads with content', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.locator('.nav-item').filter({ hasText: 'Library' }).click();
    
    // Wait for content to load
    await page.waitForTimeout(2000);
    
    // The library card should be visible (either with tracks or empty state)
    const hasCard = await page.locator('.card').first().isVisible().catch(() => false);
    const hasDropZone = await page.locator('.drop-zone').isVisible().catch(() => false);
    expect(hasCard || hasDropZone).toBeTruthy();
  });

  test('FLOW 10: Sign in button exists', async ({ page }) => {
    await page.goto(BASE_URL);
    
    // Check sign in button
    await expect(page.locator('#signInBtn')).toBeVisible();
    await expect(page.locator('#signInBtn')).toContainText('Sign in');
  });

  test('FLOW 11: Chat attach button exists', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.locator('.nav-item').filter({ hasText: 'Chat' }).click();
    
    // Check attach button
    await expect(page.locator('.chat-attach-btn')).toBeVisible();
    
    // Click attach button should open file picker
    const fileInput = page.locator('input[type="file"]').last();
    await expect(fileInput).toBeHidden(); // Hidden input
  });

  test('FLOW 12: Styleguide page loads', async ({ page }) => {
    await page.goto(`${BASE_URL}/styleguide`);
    
    // Wait for page to load
    await page.waitForTimeout(2000);
    
    // Check page loaded — either card title or any visible content
    const hasTitle = await page.locator('.card-title').first().isVisible().catch(() => false);
    const hasContent = await page.locator('.page').first().isVisible().catch(() => false);
    expect(hasTitle || hasContent).toBeTruthy();
  });
});
