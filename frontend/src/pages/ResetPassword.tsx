import { useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { apiJson } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'

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
      <div className="max-w-md mx-auto p-6">
        <h1 className="text-2xl font-semibold mb-4">Password reset</h1>
        <p className="text-muted-foreground mb-4">Your password has been reset. Redirecting to login…</p>
        <p className="mt-4">
          <Link to="/login" className="text-primary underline underline-offset-2">Go to login</Link>
        </p>
      </div>
    )
  }

  if (!token) {
    return (
      <div className="max-w-md mx-auto p-6">
        <h1 className="text-2xl font-semibold mb-4">Invalid reset link</h1>
        <p className="text-muted-foreground mb-4">This link is invalid or has expired. Request a new one from the login page.</p>
        <p className="mt-4 text-sm">
          <Link to="/forgot-password" className="text-primary underline underline-offset-2">Forgot password</Link>
          {' · '}
          <Link to="/login" className="text-primary underline underline-offset-2">Login</Link>
        </p>
      </div>
    )
  }

  return (
    <div className="max-w-md mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-4">Set new password</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="password">New password</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="confirm">Confirm password</Label>
          <Input
            id="confirm"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={8}
          />
        </div>
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <Button type="submit" disabled={loading}>
          {loading ? 'Resetting…' : 'Reset password'}
        </Button>
      </form>
      <p className="mt-4 text-sm text-muted-foreground">
        <Link to="/login" className="text-primary underline underline-offset-2">Back to login</Link>
      </p>
    </div>
  )
}
