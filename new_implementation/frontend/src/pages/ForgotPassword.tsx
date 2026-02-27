import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiJson } from '../api/client'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')
  const [resetLink, setResetLink] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await apiJson<{ message: string; reset_link?: string }>(
        '/auth/forgot_password',
        { method: 'POST', body: JSON.stringify({ email: email.trim().toLowerCase() }) }
      )
      setSent(true)
      if (data.reset_link) setResetLink(data.reset_link)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <div style={{ padding: 24, maxWidth: 400, margin: '0 auto' }}>
        <h1>Forgot password</h1>
        <p>{resetLink ? 'In development mode, use this link to reset your password:' : 'If an account exists with this email, you will receive a reset link.'}</p>
        {resetLink && (
          <p style={{ wordBreak: 'break-all', marginTop: 12 }}>
            <a href={resetLink}>{resetLink}</a>
          </p>
        )}
        <p style={{ marginTop: 16 }}>
          <Link to="/login">Back to login</Link>
        </p>
      </div>
    )
  }

  return (
    <div style={{ padding: 24, maxWidth: 400, margin: '0 auto' }}>
      <h1>Forgot password</h1>
      <p>Enter your email and we’ll send you a link to reset your password.</p>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={{ display: 'block', width: '100%', padding: 8 }}
          />
        </div>
        {error && <p style={{ color: 'red', marginBottom: 12 }}>{error}</p>}
        <button type="submit" disabled={loading} style={{ padding: '8px 16px' }}>
          {loading ? 'Sending…' : 'Send reset link'}
        </button>
      </form>
      <p style={{ marginTop: 12 }}>
        <Link to="/login">Back to login</Link>
      </p>
    </div>
  )
}
