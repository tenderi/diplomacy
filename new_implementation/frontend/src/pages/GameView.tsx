import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { apiJson } from '../api/client'

const API_BASE = import.meta.env.VITE_API_URL || ''

export default function GameView() {
  const { gameId } = useParams<{ gameId: string }>()
  const [state, setState] = useState<Record<string, unknown> | null>(null)
  const [mapUrl, setMapUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!gameId) return
    apiJson<Record<string, unknown>>(`/games/${gameId}/state`)
      .then(setState)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [gameId])

  useEffect(() => {
    if (!gameId) return
    setMapUrl(`${API_BASE}/games/${gameId}/map?t=${Date.now()}`)
  }, [gameId])

  if (loading || !state) return <div style={{ padding: 20 }}>Loading...</div>

  return (
    <div style={{ padding: 24, maxWidth: 1000, margin: '0 auto' }}>
      <p><Link to="/games">Back to games</Link></p>
      <h1>Game {gameId}</h1>
      <p>
        {String(state.current_year)} {String(state.current_season)} {String(state.current_phase)} — Turn {String(state.current_turn)}
      </p>
      {mapUrl && (
        <div style={{ marginBottom: 16 }}>
          <img src={mapUrl} alt="Game map" style={{ maxWidth: '100%', height: 'auto' }} />
        </div>
      )}
      <p>Phase: {String(state.phase_code)}</p>
    </div>
  )
}
