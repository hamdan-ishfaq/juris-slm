import { test, expect } from '@playwright/test'

// A full GPU queue answers 429 with Retry-After (D-021). The UI must say it's busy, wait, and retry on its own, without
// an error toast and without falling back to a second, non-streaming request.

test('A busy GPU is retried after Retry-After, then answered', async ({ page }) => {
  let streamCalls = 0
  let plainCalls = 0
  await page.route('**/api/v1/chat/stream', async (route) => {
    streamCalls += 1
    if (streamCalls === 1) {
      await route.fulfill({
        status: 429,
        headers: { 'Retry-After': '1', 'Content-Type': 'application/json' },
        body: JSON.stringify({ detail: 'Busy: 6 questions are ahead. Retrying in 1 s.', retry_after: 1 }),
      })
      return
    }
    const sse = [
      { type: 'token', content: 'Article 6 lists six lawful bases.' },
      { type: 'final', answer: 'Article 6 lists six lawful bases.', sources: [], answer_mode: 'llm', replaced: false },
      { type: 'done', thread_id: '00000000-0000-0000-0000-000000000000', model: 'qwen3:8b' },
    ].map((e) => `data: ${JSON.stringify(e)}\n\n`).join('')
    await route.fulfill({ status: 200, headers: { 'Content-Type': 'text/event-stream' }, body: sse })
  })
  await page.route('**/api/v1/chat', async (route) => {
    plainCalls += 1
    await route.continue()
  })

  await page.goto('/')
  await page.getByPlaceholder(/legal research/i).fill('What is lawful processing under GDPR Article 6?')
  await page.getByRole('button', { name: /^send$/i }).click()
  await expect(page.getByTestId('busy-note')).toContainText(/Busy: other questions are ahead/)
  await expect(page.locator('.answer-body').first()).toContainText('six lawful bases', { timeout: 15_000 })
  expect(streamCalls).toBe(2)
  expect(plainCalls).toBe(0)
})
