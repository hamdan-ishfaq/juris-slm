import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  // One worker: the backend serves one LLM at a time, and parallel tests asking different models make Ollama swap them.
  workers: 1,
  // LLM tests may wait for Ollama to reload a model another test swapped out (25-100 s on the 6 GB laptop GPU).
  timeout: 300_000,
  expect: { timeout: 30_000 },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.js/ },
    {
      name: 'chromium',
      use: {
        storageState: 'e2e/.auth/user.json',
      },
      dependencies: ['setup'],
      testIgnore: /auth\.setup\.js/,
    },
  ],
  webServer: process.env.CI
    ? undefined
    : {
        command: 'npm run dev',
        url: 'http://localhost:5173',
        reuseExistingServer: true,
        timeout: 120_000,
      },
})
