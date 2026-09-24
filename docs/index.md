# Diplomacy

The classic game of alliances and betrayal in 1901 Europe, played over **Telegram**
and on the web.

<div class="grid cards" markdown>

-   :material-play-circle: **New player?**

    ---

    Everything you need to start playing: joining a game with your Telegram group,
    entering orders, talking to the other powers.

    [:octicons-arrow-right-24: New player guide](NEW_USER_GUIDE.md)

-   :material-robot: **The Telegram bot**

    ---

    Open **[@IronChancellorBot](https://t.me/IronChancellorBot)** and press
    **Start**. Every command and button is listed in the reference.

    [:octicons-arrow-right-24: Bot commands](TELEGRAM_BOT_COMMANDS.md)

-   :material-web: **The website**

    ---

    A large, zoomable map, last turn's results and order entry in your browser, at
    [diplomacy.jallutähti.fi](https://diplomacy.xn--jalluthti-02a.fi).

    [:octicons-arrow-right-24: Browser client](BROWSER_CLIENT.md)

-   :material-book-open-variant: **The rules**

    ---

    The official rulebook. You don't need to memorise it: the bot only offers legal
    orders.

    [:octicons-arrow-right-24: Rulebook (PDF)](reference/rules.pdf)

</div>

## Start in three steps

1. Open **[@IronChancellorBot](https://t.me/IronChancellorBot)** in Telegram and press
   **Start**.
2. **With friends:** add the bot to your Telegram group and send `/newgame` there. Everyone
   taps **Join**. **Alone:** try **🎲 Find a game → 🎮 Solo demo**.
3. When a turn comes, tap **📝 Enter orders**: the bot goes through your units one by
   one.

## For people who run or develop it

- [Deployment](DEPLOYMENT.md): the production server, HTTPS, backups, hardening.
- [Local development](LOCAL_DEVELOPMENT.md): running everything on your own machine.
- [Design specs](specs/architecture.md): architecture, the adjudicator, the data model.

This is free software under the GNU AGPL v3 or later, based on
[diplomacy/diplomacy](https://github.com/diplomacy/diplomacy). Source code:
[github.com/tenderi/diplomacy](https://github.com/tenderi/diplomacy).
