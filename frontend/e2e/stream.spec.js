import { test, expect } from '@playwright/test'

// A chat streams a draft, then the checked answer replaces it.

test('a real question shows a draft while streaming, then the checked answer', async ({ page }) => {
  await page.goto('/')
  // A unique question, since a cached answer arrives whole, with no draft.
  const question = `When must a controller notify a personal data breach under GDPR Article 33? (run ${Date.now()})`
  await page.getByPlaceholder(/legal research/i).fill(question)
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.getByTestId('draft-answer')).toBeVisible({ timeout: 240_000 })
  await expect(page.locator('.answer-body').first()).toBeVisible({ timeout: 240_000 })
  await expect(page.getByTestId('draft-answer')).toHaveCount(0)
  expect((await page.locator('.answer-body').first().innerText()).length).toBeGreaterThan(40)
  await expect(page.getByTestId('verification-note')).toHaveText(/Not checked: whether the sources support/)
})

test('a draft the checks change is replaced, and the reader is told', async ({ page }) => {
  const events = [
    { type: 'meta', model: 'qwen3:8b' },
    { type: 'token', content: 'An unchecked draft that cites the wrong article.' },
    { type: 'final', answer: 'The checked answer from the sources.', sources: [], answer_mode: 'extractive', replaced: true },
    { type: 'done', thread_id: '00000000-0000-0000-0000-000000000000' },
  ]
  await page.route('**/api/v1/chat/stream', (route) =>
    route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(''),
    }),
  )
  await page.goto('/')
  await page.getByPlaceholder(/legal research/i).fill('What does Article 6 say?')
  await page.getByRole('button', { name: 'Send' }).click()
  await expect(page.locator('.answer-body').first()).toHaveText('The checked answer from the sources.')
  await expect(page.getByText(/the checks changed the draft/i)).toBeVisible()
  await expect(page.getByText('An unchecked draft')).toHaveCount(0)
})
