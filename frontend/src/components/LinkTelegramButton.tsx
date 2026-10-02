import { Link } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'

type Props = { variant?: 'ghost' | 'outline'; size?: 'sm' | 'default' }

/** The "Link Telegram" button: a link to the linking page until the account is linked,
 *  then an inactive button that says so. */
export function LinkTelegramButton({ variant = 'outline', size = 'default' }: Props) {
  const { user } = useAuth()
  if (user?.telegram_linked) {
    return (
      <span className="inline-flex items-center gap-2">
        <Button variant={variant} size={size} disabled aria-describedby="telegram-linked-note">
          Link Telegram
        </Button>
        <span id="telegram-linked-note" className="text-xs text-muted-foreground">
          You are already linked
        </span>
      </span>
    )
  }
  return (
    <Button variant={variant} size={size} asChild>
      <Link to="/link-telegram">Link Telegram</Link>
    </Button>
  )
}
