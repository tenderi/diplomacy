import { useState } from 'react'
import { toast } from 'sonner'
import { useAuth } from '@/contexts/AuthContext'
import { apiJson } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

/** Set or clear the nickname other players see. The system keeps no real names. */
export function NicknameForm() {
  const { user, refreshUser } = useAuth()
  const [value, setValue] = useState(user?.nickname ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function save(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      await apiJson('/auth/me', { method: 'PATCH', body: JSON.stringify({ nickname: value.trim() || null }) })
      await refreshUser()
      toast.success(value.trim() ? 'Nickname saved' : 'Nickname cleared')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the nickname')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={save} className="mb-4 max-w-sm space-y-2">
      <Label htmlFor="nickname-edit">Nickname</Label>
      <div className="flex gap-2">
        <Input id="nickname-edit" value={value} maxLength={24} onChange={(e) => setValue(e.target.value)} />
        <Button type="submit" variant="outline" disabled={saving}>
          {saving ? 'Saving...' : 'Save'}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Shown next to your power. Optional; please don't use your real name.
      </p>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </form>
  )
}
