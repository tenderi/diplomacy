import { Link } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'

export default function Home() {
  const { user, loading, logout } = useAuth()

  if (loading) return <div className="p-5">Loading...</div>

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-semibold mb-4">Diplomacy</h1>
      {user ? (
        <>
          <p className="text-muted-foreground mb-4">
            Hello, {user.full_name || user.email || 'Player'}.
          </p>
          <nav className="flex flex-wrap gap-2">
            <Button asChild>
              <Link to="/games">My games / All games</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/link-telegram">Link Telegram</Link>
            </Button>
            <Button variant="outline" onClick={logout}>
              Logout
            </Button>
          </nav>
        </>
      ) : (
        <nav className="flex flex-wrap gap-2">
          <Button asChild>
            <Link to="/login">Login</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/register">Register</Link>
          </Button>
        </nav>
      )}
    </div>
  )
}
