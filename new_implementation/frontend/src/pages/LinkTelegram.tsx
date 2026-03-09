import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { useAuth } from '@/contexts/AuthContext'
import { apiJson } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'

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
      toast.success('Link code generated')
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
      <div className="max-w-xl mx-auto">
        <h1 className="text-2xl font-semibold mb-4">Link Telegram</h1>
        <p className="text-muted-foreground mb-4">Your account is already linked to Telegram.</p>
        <Button onClick={unlinkTelegram} disabled={unlinkLoading} variant="outline" className="mr-2">
          {unlinkLoading ? 'Unlinking...' : 'Unlink Telegram'}
        </Button>
        {error && (
          <Alert variant="destructive" className="mt-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <p className="mt-4">
          <Link to="/" className="text-primary underline underline-offset-2">Back to home</Link>
        </p>
      </div>
    )
  }

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-2xl font-semibold mb-4">Link Telegram</h1>
      <p className="text-muted-foreground mb-4">
        Generate a one-time code, then in Telegram send: <strong>/link &lt;code&gt;</strong>
      </p>
      <Button onClick={generateCode} disabled={loading} className="mb-4">
        {loading ? 'Generating...' : 'Generate link code'}
      </Button>
      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {code && (
        <Card className="mt-4 bg-muted/50">
          <CardContent className="p-4">
            <p className="text-2xl tracking-widest font-mono font-semibold">{code}</p>
            <p className="text-sm text-muted-foreground mt-2">
              Valid for {Math.floor(expiresIn / 60)} minutes. In Telegram, send: <strong>/link {code}</strong>
            </p>
          </CardContent>
        </Card>
      )}
      <p className="mt-4">
        <Link to="/" className="text-primary underline underline-offset-2">Back to home</Link>
      </p>
    </div>
  )
}
