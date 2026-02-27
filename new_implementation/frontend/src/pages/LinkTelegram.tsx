import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { apiJson } from '../api/client'

export default function LinkTelegram() {
  const { user, refreshUser } = useAuth()
  const [code, setCode] = useState<string | null>(null)
  const [expiresIn, setExpiresIn] = useState(0)
  const [loading, setLoading] = useState(false)
  const [unlinkLoading, setUnlinkLoading] = useState(false)
  const [error, setError] = useState('')

  async function generateCode() {
    setError('')
    setLoading(true)
    try {
      const data = await apiJson<{ code: string; expires_in_seconds: number }>(
        '/auth/me/link_code',
        { method: 'POST' }
      )
      setCode(data.code)
      setExpiresIn(data.expires_in_seconds)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate code')
    } finally {
      setLoading(false)
    }
  }

  async function unlinkTelegram() {
    setError('')
    setUnlinkLoading(true)
    try {
      await apiJson<{ status: string; message: string }>('/auth/me/unlink_telegram', { method: 'POST' })
      await refreshUser()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to unlink')
    } finally {
      setUnlinkLoading(false)
    }
  }

  if (user?.telegram_linked) {
    return (
      <div style={{ padding: 24, maxWidth: 500, margin: '0 auto' }}>
        <h1>Link Telegram</h1>
        <p>Your account is already linked to Telegram.</p>
        <button
          type="button"
          onClick={unlinkTelegram}
          disabled={unlinkLoading}
          style={{ padding: '8px 16px', marginTop: 8, marginRight: 8 }}
        >
          {unlinkLoading ? 'Unlinking...' : 'Unlink Telegram'}
        </button>
        {error && <p style={{ color: 'red', marginTop: 12 }}>{error}</p>}
        <p style={{ marginTop: 16 }}>
          <Link to="/">Back to home</Link>
        </p>
      </div>
    )
  }

  return (
    <div style={{ padding: 24, maxWidth: 500, margin: '0 auto' }}>
      <h1>Link Telegram</h1>
      <p>Generate a one-time code, then in Telegram send: <strong>/link &lt;code&gt;</strong></p>
      <button type="button" onClick={generateCode} disabled={loading} style={{ padding: '8px 16px', marginBottom: 12 }}>
        {loading ? 'Generating...' : 'Generate link code'}
      </button>
      {error && <p style={{ color: 'red', marginBottom: 12 }}>{error}</p>}
      {code && (
        <div style={{ background: '#f0f0f0', padding: 16, borderRadius: 8, marginTop: 12 }}>
          <p style={{ margin: 0, fontSize: 24, letterSpacing: 4, fontFamily: 'monospace' }}>{code}</p>
          <p style={{ margin: '8px 0 0', fontSize: 14, color: '#666' }}>
            Valid for {Math.floor(expiresIn / 60)} minutes. In Telegram, send: <strong>/link {code}</strong>
          </p>
        </div>
      )}
      <p style={{ marginTop: 16 }}>
        <Link to="/">Back to home</Link>
      </p>
    </div>
  )
}
