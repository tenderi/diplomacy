import { Routes, Route, Navigate, useParams } from 'react-router'
import { useAuth } from './contexts/AuthContext'
import { AppLayout } from './components/AppLayout'
import { Toaster } from './components/ui/sonner'
import Home from './pages/Home'
import Login from './pages/Login'
import Register from './pages/Register'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import LinkTelegram from './pages/LinkTelegram'
import GameList from './pages/GameList'
import GameView from './pages/GameView'
import Feedback from './pages/Feedback'
import Sandbox from './pages/Sandbox'

// Remount per game: GameView keeps the previous board on screen during a refresh, which
// must not carry over to a different game reached by an in-app link.
function GameViewForRoute() {
  const { gameId } = useParams()
  return <GameView key={gameId} />
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="p-5">Loading...</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
  <>
    <AppLayout>
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route
        path="/link-telegram"
        element={
          <ProtectedRoute>
            <LinkTelegram />
          </ProtectedRoute>
        }
      />
      <Route
        path="/games"
        element={
          <ProtectedRoute>
            <GameList />
          </ProtectedRoute>
        }
      />
      <Route
        path="/games/:gameId"
        element={
          <ProtectedRoute>
            <GameViewForRoute />
          </ProtectedRoute>
        }
      />
      <Route
        path="/sandbox"
        element={
          <ProtectedRoute>
            <Sandbox />
          </ProtectedRoute>
        }
      />
      <Route
        path="/feedback"
        element={
          <ProtectedRoute>
            <Feedback />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </AppLayout>
    <Toaster richColors position="bottom-center" />
  </>
  )
}
