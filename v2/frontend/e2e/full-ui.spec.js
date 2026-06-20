/**
 * Full UI regression — every nav view + core workflows (dev master / owner).
 */
import { test, expect } from '@playwright/test'
import path from 'path'
import { readFile } from 'fs/promises'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

const API = process.env.PLAYWRIGHT_API_URL || 'http://localhost:8002'
const EMAIL = process.env.VITE_DEV_EMAIL || 'devmaster@example.com'

async function apiOk(request) {
  try {
    const r = await request.get(`${API}/health`)
    return r.ok()
  } catch {
    return false
  }
}

async function navTo(page, label) {
  await page.locator('button.nav-item').filter({ has: page.getByText(label, { exact: true }) }).click()
}

test.describe('Full UI suite', () => {
  test.beforeEach(async ({ page, request }) => {
    test.skip(!(await apiOk(request)), 'API not reachable')
    page.on('dialog', (d) => d.accept())
    await page.goto('/')
    await expect(page.locator('button.nav-item').filter({ has: page.getByText('Research', { exact: true }) })).toBeVisible({ timeout: 15_000 })
  })

  test('Research — law corpus chat', async ({ page }) => {
    await navTo(page, 'Research')
    await expect(page.getByText(/research assistant/i)).toBeVisible()
    await page.getByPlaceholder(/legal research/i).fill('What is lawful processing under GDPR Article 6?')
    await page.getByRole('button', { name: /^send$/i }).click()
    await expect(page.locator('.answer-body').first()).toBeVisible({ timeout: 120_000 })
    expect((await page.locator('.answer-body').first().innerText()).length).toBeGreaterThan(40)
  })

  test('Matters — create, upload, deadline, analyze', async ({ page, request }) => {
    await navTo(page, 'Matters')
    await expect(page.getByText(/matter workspace/i)).toBeVisible()

    await page.getByRole('button', { name: /new matter/i }).click()
    await expect(page.getByText(/drop files here/i)).toBeVisible({ timeout: 15_000 })

    const fixture = path.join(__dirname, 'fixtures', 'sample_nda.txt')
    const uploadResp = page.waitForResponse(
      (r) => /\/api\/v1\/matters\/[^/]+\/documents$/.test(new URL(r.url()).pathname)
        && r.request().method() === 'POST'
        && r.status() === 200,
      { timeout: 60_000 },
    )
    const [fileChooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      page.getByRole('button', { name: /upload document/i }).click(),
    ])
    await fileChooser.setFiles(fixture)
    const upload = await uploadResp
    const uploadJson = await upload.json()
    const matterId = uploadJson.matter_id
    const docId = uploadJson.id
    const token = await page.evaluate(() => localStorage.getItem('token'))

    await expect.poll(async () => {
      const r = await request.get(`${API}/api/v1/matters/${matterId}/documents/${docId}/status`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      return (await r.json()).status
    }, { timeout: 120_000, intervals: [2000] }).toBe('processed')

    await page.reload()
    await expect(page.locator('button.nav-item').filter({ has: page.getByText('Matters', { exact: true }) })).toBeVisible()
    await navTo(page, 'Matters')
    await page.locator('.matters-toolbar select').first().selectOption(matterId)
    await expect(page.locator('.doc-table .status-badge').first()).toHaveText(/processed/i, { timeout: 30_000 })

    await page.getByPlaceholder(/deadline title/i).fill('UI test filing')
    const due = new Date()
    due.setMonth(due.getMonth() + 1)
    await page.locator('input[type="date"]').fill(due.toISOString().slice(0, 10))
    await page.getByRole('button', { name: /^add$/i }).click()
    await expect(page.getByText(/UI test filing/i)).toBeVisible()

    await page.locator('.doc-table table tbody tr').first().click()
    await page.getByRole('button', { name: /analyze clauses/i }).click()
    await expect(page.locator('.analyze-section').first()).toBeVisible({ timeout: 120_000 })
  })

  test('Clause bank — add and list', async ({ page }) => {
    await navTo(page, 'Clause bank')
    await expect(page.getByRole('heading', { name: 'Clause bank', exact: true }).nth(1)).toBeVisible()
    const title = `UI Standard NDA ${Date.now()}`
    await page.getByPlaceholder(/^title$/i).fill(title)
    await page.getByPlaceholder(/clause body/i).fill('Receiving Party shall not disclose Confidential Information.')
    await page.getByRole('button', { name: /save clause/i }).click()
    await expect(page.getByText(title)).toBeVisible({ timeout: 15_000 })
  })

  test('Corpus — stats and admin upload form', async ({ page }) => {
    await navTo(page, 'Corpus')
    await expect(page.getByRole('heading', { name: 'Corpus' })).toBeVisible({ timeout: 30_000 })
    await expect(page.getByText(/total chunks/i)).toBeVisible()
    await expect(page.getByText(/upload law corpus/i)).toBeVisible()
  })

  test('Graph — extract and load', async ({ page, request }) => {
    const token = await page.evaluate(() => localStorage.getItem('token'))
    const headers = { Authorization: `Bearer ${token}` }

    let matterId = ''
    let docId = ''
    const matters = await request.get(`${API}/api/v1/matters`, { headers }).then((r) => r.json())
    for (const m of matters) {
      const docs = await request.get(`${API}/api/v1/matters/${m.id}/documents`, { headers }).then((r) => r.json())
      const hit = docs.find((d) => d.ingest_status === 'processed')
      if (hit) {
        matterId = m.id
        docId = hit.id
        break
      }
    }

    if (!docId) {
      const m = await request.post(`${API}/api/v1/matters`, {
        headers,
        data: { name: `Graph E2E ${Date.now()}`, description: 'graph test' },
      }).then((r) => r.json())
      matterId = m.id
      const fixture = path.join(__dirname, 'fixtures', 'sample_nda.txt')
      const up = await request.post(`${API}/api/v1/matters/${matterId}/documents`, {
        headers,
        multipart: {
          file: { name: 'sample_nda.txt', mimeType: 'text/plain', buffer: await readFile(fixture) },
          confidentiality: 'internal',
        },
      })
      docId = (await up.json()).id
      await expect.poll(async () => {
        const st = await request.get(`${API}/api/v1/matters/${matterId}/documents/${docId}/status`, { headers })
        return (await st.json()).status
      }, { timeout: 120_000, intervals: [2000] }).toBe('processed')
    }

    await navTo(page, 'Graph')
    await page.locator('.matters-toolbar select').first().selectOption(matterId)
    await page.locator('.matters-toolbar select').nth(1).selectOption(docId)
    await page.getByRole('button', { name: /extract graph/i }).click()
    await expect(page.locator('.entity-list li').first()).toBeVisible({ timeout: 60_000 })
  })

  test('Audit — list for admin', async ({ page }) => {
    await navTo(page, 'Audit')
    await expect(page.getByRole('heading', { name: 'Audit trail' })).toBeVisible({ timeout: 15_000 })
    await expect(page.getByRole('button', { name: /export csv/i })).toBeVisible()
  })

  test('Admin — users table', async ({ page }) => {
    await navTo(page, 'Admin')
    await expect(page.getByRole('heading', { name: /administration/i })).toBeVisible()
    await expect(page.getByRole('cell', { name: EMAIL })).toBeVisible({ timeout: 15_000 })
  })

  test('Help — guide content', async ({ page }) => {
    await navTo(page, 'Help')
    await expect(page.getByRole('heading', { name: /user guide/i })).toBeVisible()
    await expect(page.getByText(/two modes/i)).toBeVisible()
  })

  test('System — GPU hardware panel', async ({ page }) => {
    await navTo(page, 'System')
    await expect(page.getByRole('heading', { name: 'System' })).toBeVisible()
    const panel = page.getByTestId('hardware-panel')
    await expect(panel).toBeVisible({ timeout: 15_000 })
    const hwText = await panel.innerText()
    expect(hwText.toLowerCase()).toMatch(/cuda/)
    expect(hwText.toLowerCase()).toMatch(/embedding/)
    expect(hwText.toLowerCase()).toMatch(/cuda|available/)
  })

  test('Logout and re-login', async ({ page }) => {
    await page.getByRole('button', { name: /sign out/i }).click()
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible({ timeout: 10_000 })
  })
})
