import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { apiJson } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

/** `GET /games/{id}/channel`: players of the game only (403 for anyone else). */
export type ChannelInfo = {
  linked: boolean
  bot_username: string
  channel_id?: string
  channel_name?: string | null
}

/** The game's Telegram group, for a player of the game: the linked group with an Unlink
 *  button, or a link that opens Telegram to pick a group (the bot links it there, from
 *  `/start link_<id>`). Renders nothing until the API answers, or if it refuses. */
export function TelegramGroupCard({ gameId }: { gameId: string }) {
  const [info, setInfo] = useState<ChannelInfo | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    apiJson<ChannelInfo>(`/games/${gameId}/channel`)
      .then(setInfo)
      .catch(() => setInfo(null))
  }, [gameId])

  useEffect(() => { load() }, [load])

  if (!info) return null

  const unlink = async () => {
    setBusy(true)
    try {
      await apiJson(`/games/${gameId}/channel/unlink`, { method: 'DELETE' })
      toast.success('The Telegram group is unlinked.')
      load()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not unlink the group')
    } finally {
      setBusy(false)
    }
  }

  const linkUrl = `https://t.me/${encodeURIComponent(info.bot_username)}?startgroup=link_${encodeURIComponent(gameId)}`

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Telegram group</CardTitle>
        {info.linked ? (
          <CardDescription>
            This game is linked to{' '}
            <span className="font-medium text-foreground">{info.channel_name || `group ${info.channel_id}`}</span>.
          </CardDescription>
        ) : (
          <CardDescription>
            Opens Telegram to pick a group: the bot is added to it and links this game there,
            since you play in it.
          </CardDescription>
        )}
      </CardHeader>
      <CardContent>
        {info.linked ? (
          <Button variant="outline" onClick={unlink} disabled={busy}>
            Unlink
          </Button>
        ) : (
          <Button variant="outline" asChild>
            <a href={linkUrl} target="_blank" rel="noopener noreferrer">
              Link a Telegram group
            </a>
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
