import { MemoryRouter } from 'react-router-dom';
import { act, render, screen, waitFor } from '@testing-library/react';

import Chat from '../pages/Chat';

const mockGetChatHistory = vi.fn();
const mockClearChatHistory = vi.fn();
const mockQuery = vi.fn();

vi.mock('../lib/api', () => ({
  queryAPI: {
    getChatHistory: (...args) => mockGetChatHistory(...args),
    clearChatHistory: (...args) => mockClearChatHistory(...args),
    query: (...args) => mockQuery(...args),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

describe('Chat page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('loads history on mount and renders history messages', async () => {
    mockGetChatHistory.mockResolvedValueOnce({
      data: {
        messages: [
          { role: 'user', content: 'Loaded user message', created_at: '2026-02-20T00:00:00Z' },
          { role: 'assistant', content: 'Loaded assistant message', created_at: '2026-02-20T00:00:01Z' },
        ],
      },
    });

    render(
      <MemoryRouter>
        <Chat />
      </MemoryRouter>
    );

    await waitFor(() => expect(mockGetChatHistory).toHaveBeenCalledWith(50));
    expect(await screen.findByText('Loaded user message')).toBeInTheDocument();
    expect(await screen.findByText('Loaded assistant message')).toBeInTheDocument();
  });

  it('shows loading skeleton placeholders while history is pending', async () => {
    let resolveHistory;
    const historyPromise = new Promise((resolve) => {
      resolveHistory = resolve;
    });
    mockGetChatHistory.mockReturnValueOnce(historyPromise);

    const { container } = render(
      <MemoryRouter>
        <Chat />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(container.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0);
    });

    await act(async () => {
      resolveHistory({ data: { messages: [] } });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(container.querySelectorAll('.animate-pulse').length).toBe(0);
    });
  });
});