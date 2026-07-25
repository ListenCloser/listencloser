import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Home from '@/app/page'

vi.mock('@/components/Studio', () => ({
  default: () => <div data-testid="studio-mock">Studio</div>,
}))

vi.mock('@/components/AuthProvider', () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({ user: { id: 'test' }, session: {}, loading: false, signOut: vi.fn() }),
}))

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), back: vi.fn(), forward: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
}))

describe('Home (page)', () => {
  beforeEach(() => {
    vi.unstubAllEnvs()
  })

  it('renders Studio when authenticated', () => {
    render(<Home />)
    expect(screen.getByTestId('studio-mock')).toBeInTheDocument()
  })

  it('renders Studio when unauthenticated and auth is not bypassed', async () => {
    vi.stubEnv('NODE_ENV', 'production')
    vi.stubEnv('NEXT_PUBLIC_MOCK_ENABLED', 'false')
    const useAuthMod = await import('@/components/AuthProvider')
    vi.spyOn(useAuthMod, 'useAuth').mockReturnValue({
      user: null,
      session: null,
      loading: false,
      signOut: vi.fn(),
    })
    render(<Home />)
    expect(screen.getByTestId('studio-mock')).toBeInTheDocument()
  })
})
