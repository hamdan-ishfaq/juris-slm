import { test, expect } from '@playwright/test'

const API = process.env.PLAYWRIGHT_API_URL || 'http://localhost:8002'

test('login and research chat', async ({ page, request }) => {
  const health = await request.get(`${API}/health`)
  test.skip(!health.ok(), 'API not reachable')

  await page.goto('/')
  await expect(page.locator('button.nav-item').filter({ has: page.getByText('Research', { exact: true }) })).toBeVisible({ timeout: 15_000 })

  await page.getByPlaceholder(/legal research/i).fill('What is lawful processing under GDPR Article 6?')
  await page.getByRole('button', { name: /^send$/i }).click()
  await expect(page.locator('.answer-body').first()).toBeVisible({ timeout: 120_000 })
})

test('branding endpoint is public', async ({ request }) => {
  const health = await request.get(`${API}/health`)
  test.skip(!health.ok(), 'API not reachable')
  const r = await request.get(`${API}/api/v1/config/branding`)
  expect(r.ok()).toBeTruthy()
  const body = await r.json()
  expect(body.brand_name).toBeTruthy()
})

test('matter upload mock txt', async ({ page, request }) => {
  const health = await request.get(`${API}/health`)
  test.skip(!health.ok(), 'API not reachable')

  await page.goto('/')
  await expect(page.locator('button.nav-item').filter({ has: page.getByText('Matters', { exact: true }) })).toBeVisible({ timeout: 15_000 })
  await page.locator('button.nav-item').filter({ has: page.getByText('Matters', { exact: true }) }).click()
  await page.getByRole('button', { name: /new matter/i }).click()
  await expect(page.getByText(/matter workspace/i)).toBeVisible()
})
