import { expect, test } from '@playwright/test';

test('critical path smoke: register/login, chat round-trip, persistence', async ({ page }) => {
  const runId = Date.now();
  const email = `e2e_${runId}@example.com`;
  const password = `E2ePass!${runId}`;
  const probeMessage = 'Hello System Check';

  await test.step('Login handshake', async () => {
    await page.goto('/');
    await page.getByRole('link', { name: /get started|login/i }).first().click();

    await expect(page).toHaveURL(/\/login$/);

    const registerResponsePromise = page.waitForResponse(
      (response) => response.url().includes('/auth/register') && response.request().method() === 'POST'
    );

    const tokenResponsePromise = page.waitForResponse(
      (response) => {
        if (response.request().method() !== 'POST') {
          return false;
        }
        return response.url().includes('/auth/token') || response.url().includes('/auth/login');
      }
    );

    await page.getByRole('button', { name: /sign up/i }).click();
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password').fill(password);
    await page.getByRole('button', { name: /^sign up$/i }).click();

    const registerResponse = await registerResponsePromise;
    expect(registerResponse.status()).toBe(201);

    const tokenResponse = await tokenResponsePromise;
    expect(tokenResponse.status()).toBe(200);

    await expect(page).toHaveURL(/\/$/);
    await page.goto('/chat');
    await expect(page).toHaveURL(/\/chat$/);
  });

  await test.step('Chat loop frontend-backend', async () => {
    const input = page.getByPlaceholder('Ask a legal question...');
    await input.fill(probeMessage);
    await page.getByRole('button', { name: /send/i }).click();

    await expect(page.getByText(/Analyzing|Thinking/i)).toBeVisible();

    await expect(async () => {
      await expect(page.getByText(probeMessage)).toBeVisible();

      const messages = await page.locator('p.text-sm.leading-relaxed').allTextContents();
      const hasAssistantReply = messages.some(
        (text) =>
          text &&
          text !== probeMessage &&
          !text.includes('Welcome to BEWEIS') &&
          !text.toLowerCase().startsWith('error:')
      );
      expect(hasAssistantReply).toBeTruthy();
    }).toPass({ timeout: 30_000 });
  });

  await test.step('Persistence check', async () => {
    await page.reload();
    await expect(page.getByText(probeMessage)).toBeVisible({ timeout: 15_000 });
  });
});