import { test, expect } from '@playwright/test'

// The System page must say the LLM's GPU share is unknown when Ollama doesn't answer, not show a stale "100%".

test('GPU share reads unknown when Ollama is unreachable', async ({ page }) => {
  await page.route('**/api/v1/status', async (route) => {
    const response = await route.fetch()
    const body = await response.json()
    body.hardware = { ...body.hardware, llm_loaded: null }
    await route.fulfill({ response, json: body })
  })
  await page.goto('/')
  await page.locator('button.nav-item').filter({ has: page.getByText('System', { exact: true }) }).click()
  const panel = page.getByTestId('hardware-panel')
  await expect(panel).toContainText(/GPU share unknown/)
  await expect(panel).not.toContainText(/% on the GPU/)
})
