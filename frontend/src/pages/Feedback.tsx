import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiJson } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Alert, AlertDescription } from '@/components/ui/alert'

/** Mirrors the API's cap (routes/feedback.py MAX_FEEDBACK_CHARS). */
export const MAX_FEEDBACK_CHARS = 2000

/**
 * A report to the maintainer. `?game=N` (the footer link adds it on a game
 * page) attaches that game; the server records its phase.
 */
export default function Feedback() {
  const [params] = useSearchParams()
  const gameId = params.get('game')
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await apiJson('/feedback', {
        method: 'POST',
        body: JSON.stringify({ text: text.trim(), game_id: gameId, source: 'web' }),
      })
      setSent(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <div className="max-w-md mx-auto p-6">
        <h1 className="text-2xl font-semibold mb-4">Thanks!</h1>
        <p className="text-muted-foreground mb-4">Your feedback has been sent to the maintainer.</p>
        <Link
          to={gameId ? `/games/${gameId}` : '/games'}
          className="text-primary underline underline-offset-2"
        >
          {gameId ? `Back to game ${gameId}` : 'Back to your games'}
        </Link>
      </div>
    )
  }

  return (
    <div className="max-w-md mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-4">Send feedback</h1>
      <p className="text-muted-foreground mb-4">
        Something wrong, confusing, or good? Say what you did, what you expected and what
        happened.{gameId ? ` Game ${gameId} and its current phase are attached.` : ''}
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="feedback">Your feedback</Label>
          <Textarea
            id="feedback"
            value={text}
            maxLength={MAX_FEEDBACK_CHARS}
            rows={6}
            onChange={(e) => setText(e.target.value)}
            required
          />
        </div>
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <Button type="submit" disabled={loading || !text.trim()}>
          {loading ? 'Sending...' : 'Send'}
        </Button>
      </form>
    </div>
  )
}
