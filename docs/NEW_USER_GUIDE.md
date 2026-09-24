# Playing Diplomacy: a guide for new players

Welcome to the beta! This guide covers everything you need to start playing.
Most of it happens in Telegram, with the bot **[@IronChancellorBot](https://t.me/IronChancellorBot)**.
There is also a website, **https://diplomacy.xn--jalluthti-02a.fi**, which is optional.

---

## 1. Diplomacy in one minute

Seven great powers of 1901 Europe (England, France, Germany, Italy, Austria, Russia,
Turkey) compete to control **18 of the 34 supply centres**. Each turn, every player
secretly writes orders for all their armies and fleets. Then all orders are revealed and
resolved **at the same time**. There is no dice and no luck. The only way to get ahead
is to make deals with other players, and to decide which deals to keep.

The official rulebook: [docs/reference/rules.pdf](reference/rules.pdf). You don't need
to know the rules by heart: the bot only ever offers you legal orders.

---

## 2. Get started (1 minute)

1. Open **[@IronChancellorBot](https://t.me/IronChancellorBot)** in Telegram and press **Start**.
   That's it: you're registered, and three keys appear under the chat:
   - **🎮 My games**: your games. Open one to do anything in it.
   - **🎲 Find a game**: games you can join, the queue for a new game, and a solo demo.
   - **ℹ️ Help**: every command.
2. Want to try it alone first? **🎲 Find a game → 🎮 Solo demo**. You play Germany against
   six computer-played powers, and each turn runs as soon as your orders are in.

---

## 3. Playing with your Telegram group

This is how most beta games work. It needs one person, the **organiser**, to set it up.

**Organiser:**
1. Add **@IronChancellorBot** to your Telegram group (group menu → *Add members*).
2. In the group, send **`/newgame`**.
3. The bot posts **"Game N for this group"** with a **🎮 Join this game** button.

**Everyone (including the organiser):**
4. Tap **🎮 Join this game**. It opens your *private* chat with the bot, where you pick a
   power.
5. The game begins when all seven powers are taken.
   - With fewer than seven players, the organiser can leave empty powers to
     *civil disorder*: in their private chat, `/dummy N TURKEY` (for example). Those
     powers' units just hold.

**What happens where:**

| In the group (everyone sees) | In your private chat with the bot (only you) |
|---|---|
| "Game N is full: the game has begun!" | Your orders |
| Turn results and the new map | Your private messages to other powers |
| Deadline reminders | The game menu, your status, "wait for me" |
| Broadcasts ("to everyone") from players | Notifications with an **Enter orders** button |

The group's games are **only visible to the group's members**. Nobody else can find or
join them. If you type an order command in the group by mistake, the bot won't take it:
it points you to your private chat, because everyone in the group would see it.

---

## 4. A turn, step by step

1. **You get a message:** "The turn has been processed for game N. Your next orders are
   due." It comes with **📝 Enter orders**. The group gets the map and a
   **📝 Send my orders** link that opens your private chat.
2. **Tap 📝 Enter orders.** The bot goes through your units **one at a time** and shows
   only the orders that unit can legally give:
   - **Hold**, **move to** a neighbouring province;
   - **🤝 Support options**: help another unit hold, or help its move;
   - **🚢 Convoy options** (fleets): carry an army across the sea.

   **⬅️ Back** and **⏭ Skip** are on every step. At the end you see all your orders
   together. Tap **✅ Submit**.
3. **Changed your mind?** Enter orders again: a new order for a unit replaces its old one.
   **📋 My orders** in the game menu shows what you've sent, and can clear it.
4. **The turn runs** as soon as every player has sent orders for all their units, or at
   the deadline if the group set one. Until then nothing is final.
   - Still negotiating? In the game menu, tap **✋ Wait for me before processing**. The
     turn then waits for you, though a deadline still applies. Tap **✅ I'm ready**
     when you're done.
5. After movement there may be a short **retreat** phase (a dislodged unit must move or
   disband), and after autumn a **build** phase (gain or lose units to match your supply
   centres). The bot asks for exactly what's needed; most players have nothing to do.

**Prefer typing?** `/orders A PAR - BUR; F BRE - MAO; A MAR S A PAR - BUR`. Examples
are under `/examples`.

---

## 5. Talking: the actual game

- **Private messages:** game menu → **💬 Messages** → tap a power, then just type your
  message. Only that player sees it.
- **To everyone:** **💬 Messages → 📣 Everyone**. It's also posted in the group.
- Or by command: `/message FRANCE Shall we split the Low Countries?`, `/broadcast Peace in our time.`

Deals are not binding, and neither are promises. That's the game.

---

## 6. Deadlines, draws, and leaving

- **Deadline:** game menu → **⏰ Deadline**. Propose 12 h, 24 h or 48 h. It applies
  when a majority of players agree (**✅/❌ Vote** buttons). Ten minutes before a
  deadline, everyone gets a reminder. Units without orders hold.
- **Draw:** `/draw` votes to end the game as a shared draw. It ends when every surviving
  power agrees. `/nodraw` takes your vote back.
- **Leaving:** `/quit N`. Your power becomes free for someone else to take over.

---

## 7. The website (optional)

At **https://diplomacy.xn--jalluthti-02a.fi** you can see your games with a large,
zoomable map, results of the last turn, messages, and order entry.

1. **Register** with your email and a password.
2. **Link Telegram** (top menu): the site shows a code; send `/link <code>` to the bot.
   Your web account and your Telegram player are now the same, and your games appear
   on both.
3. **Forgot your password?** *Login → Forgot password?* The reset link comes as a
   Telegram message from the bot, if your account is linked (otherwise by email).

Group games can't be joined from the website. Join them through the group's button.

---

## 8. Good to know

- **You can't break anything.** The bot only offers legal orders, and a typed order that
  isn't legal is rejected with the reason.
- **Several games?** Your commands act on your *current game*: the one you last opened
  or were notified about. Switch with **🎮 My games** or `/game N`.
- **The server restarting** (after an update, usually a minute) doesn't lose anything:
  orders and messages you send meanwhile are queued and delivered, and the bot tells you.
  `/queue` shows what's waiting.
- **Your data:** your Telegram name and ID, your orders and messages, and, if you use the
  website, your email address and a hashed password.

## 9. Beta: something odd?

Tell the organiser or the maintainer what you did, what you expected and what happened,
ideally with a screenshot and the game number. This is free software (GNU AGPL v3 or
later); the source is at https://github.com/tenderi/diplomacy.

**Quick reference:** [all bot commands](TELEGRAM_BOT_COMMANDS.md) · [the rules](reference/rules.pdf)
