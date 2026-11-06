import { test as setup, expect } from '@playwright/test'

const EMAIL = process.env.VITE_DEV_EMAIL || 'devmaster@example.com'
const PASSWORD = process.env.VITE_DEV_PASSWORD || 'DevMasterPass123!'

setup('authenticate dev master', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel(/email/i).fill(EMAIL)
  await page.getByLabel(/password/i).fill(PASSWORD)
  await page.getByRole('button', { name: /sign in/i }).click()
  await expect(page.locator('button.nav-item').filter({ has: page.getByText('Research', { exact: true }) })).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('button.nav-item').filter({ has: page.getByText('Corpus', { exact: true }) })).toBeVisible({ timeout: 15_000 })
  await page.context().storageState({ path: 'e2e/.auth/user.json' })
})
