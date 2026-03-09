import { Link } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth()

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
    </div>
  )
}
