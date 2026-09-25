import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'

export const SOURCE_URL = 'https://github.com/tenderi/diplomacy'

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth()
  // On a game page, feedback is about that game.
  const gameMatch = useLocation().pathname.match(/^\/games\/([^/]+)/)
  const feedbackTo = gameMatch ? `/feedback?game=${encodeURIComponent(gameMatch[1])}` : '/feedback'

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-border bg-card px-4 py-3">
        <div className="max-w-4xl mx-auto flex flex-wrap items-center justify-between gap-3">
          <Link to="/" className="text-lg font-semibold text-foreground hover:text-primary">
            Diplomacy
          </Link>
          <nav className="flex flex-wrap items-center gap-2">
            {loading ? (
              <span className="text-muted-foreground text-sm">Loading...</span>
            ) : user ? (
              <>
                <Button variant="ghost" size="sm" asChild>
                  <Link to="/games">Games</Link>
                </Button>
                <Button variant="ghost" size="sm" asChild>
                  <Link to="/link-telegram">Link Telegram</Link>
                </Button>
                <Button variant="outline" size="sm" onClick={logout}>
                  Logout
                </Button>
              </>
            ) : (
              <>
                <Button variant="ghost" size="sm" asChild>
                  <Link to="/login">Login</Link>
                </Button>
                <Button variant="default" size="sm" asChild>
                  <Link to="/register">Register</Link>
                </Button>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-6">
        {children}
      </main>
      {/* The AGPL (section 13) requires offering the source to everyone who uses
          the program over a network. A modified deployment must point this at
          its own source. */}
      <footer className="border-t border-border px-4 py-3 text-xs text-muted-foreground">
        <div className="max-w-4xl mx-auto flex flex-wrap gap-x-3 gap-y-1">
          {user && (
            <Link to={feedbackTo} className="underline underline-offset-2 hover:text-foreground">
              Send feedback
            </Link>
          )}
          <span>Free software under the GNU AGPL v3 or later</span>
          <a href={SOURCE_URL} className="underline underline-offset-2 hover:text-foreground">
            Source code
          </a>
          <span>
            Based on{' '}
            <a
              href="https://github.com/diplomacy/diplomacy"
              className="underline underline-offset-2 hover:text-foreground"
            >
              diplomacy/diplomacy
            </a>
          </span>
        </div>
      </footer>
    </div>
  )
}
