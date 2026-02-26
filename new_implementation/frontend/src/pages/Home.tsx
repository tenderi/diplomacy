import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function Home() {
  const { user, loading, logout } = useAuth()

  if (loading) return <div style={{ padding: 20 }}>Loading...</div>

  return (
    <div style={{ padding: 24, maxWidth: 600, margin: '0 auto' }}>
      <h1>Diplomacy</h1>
      {user ? (
        <>
          <p>Hello, {user.full_name || user.email || 'Player'}.</p>
          <nav style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <Link to="/games">My games / All games</Link>
            <Link to="/link-telegram">Link Telegram</Link>
            <button type="button" onClick={logout}>
              Logout
            </button>
          </nav>
        </>
      ) : (
        <nav style={{ display: 'flex', gap: 12 }}>
          <Link to="/login">Login</Link>
          <Link to="/register">Register</Link>
        </nav>
      )}
    </div>
  )
}
