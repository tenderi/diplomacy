import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiJson } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'

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
      <div className="max-w-md mx-auto p-6">
        <h1 className="text-2xl font-semibold mb-4">Forgot password</h1>
        {resetLink ? (
          <p className="text-muted-foreground mb-4">In development mode, use this link to reset your password:</p>
        ) : (
          <>
            <p className="text-muted-foreground mb-2">
              If an account exists with this email, a reset link is on its way: as a Telegram
              message from the Diplomacy bot if your account is linked to Telegram, otherwise by
              email.
            </p>
            <p className="text-muted-foreground mb-4">
              The link works once, for one hour. Nothing arrived? Check Telegram and your spam
              folder, or ask again in a few minutes.
            </p>
          </>
        )}
        {resetLink && (
          <p className="break-all mt-4">
            <a href={resetLink} className="text-primary underline underline-offset-2">{resetLink}</a>
          </p>
        )}
        <p className="mt-4">
          <Link to="/login" className="text-primary underline underline-offset-2">Back to login</Link>
        </p>
      </div>
    )
  }

  return (
    <div className="max-w-md mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-4">Forgot password</h1>
      <p className="text-muted-foreground mb-4">
        Enter your account&apos;s email and we&apos;ll send you a link to choose a new password &mdash;
        through the Diplomacy Telegram bot if your account is linked to Telegram, otherwise by
        email.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <Button type="submit" disabled={loading}>
          {loading ? 'Sending…' : 'Send reset link'}
        </Button>
      </form>
      <p className="mt-4 text-sm text-muted-foreground">
        <Link to="/login" className="text-primary underline underline-offset-2">Back to login</Link>
      </p>
    </div>
  )
}
