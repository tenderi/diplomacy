import { useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { apiJson } from '../api/client'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    if (!token) {
      setError('Invalid reset link (missing token)')
      return
    }
    setLoading(true)
    try {
      await apiJson<{ message: string }>('/auth/reset_password', {
        method: 'POST',
        body: JSON.stringify({ token, new_password: password }),
      })
      setDone(true)
      setTimeout(() => navigate('/login'), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reset failed')
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <div style={{ padding: 24, maxWidth: 400, margin: '0 auto' }}>
        <h1>Password reset</h1>
        <p>Your password has been reset. Redirecting to login…</p>
        <p style={{ marginTop: 12 }}>
          <Link to="/login">Go to login</Link>
        </p>
      </div>
    )
  }

  if (!token) {
    return (
      <div style={{ padding: 24, maxWidth: 400, margin: '0 auto' }}>
        <h1>Invalid reset link</h1>
        <p>This link is invalid or has expired. Request a new one from the login page.</p>
        <p style={{ marginTop: 12 }}>
          <Link to="/forgot-password">Forgot password</Link> · <Link to="/login">Login</Link>
        </p>
      </div>
    )
  }

  return (
    <div style={{ padding: 24, maxWidth: 400, margin: '0 auto' }}>
      <h1>Set new password</h1>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="password">New password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            style={{ display: 'block', width: '100%', padding: 8 }}
          />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="confirm">Confirm password</label>
          <input
            id="confirm"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={8}
            style={{ display: 'block', width: '100%', padding: 8 }}
          />
        </div>
        {error && <p style={{ color: 'red', marginBottom: 12 }}>{error}</p>}
        <button type="submit" disabled={loading} style={{ padding: '8px 16px' }}>
          {loading ? 'Resetting…' : 'Reset password'}
        </button>
      </form>
      <p style={{ marginTop: 12 }}>
        <Link to="/login">Back to login</Link>
      </p>
    </div>
  )
}
