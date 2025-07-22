# Telegram Channel Integration Specification

## Overview

This specification defines how the Diplomacy bot can integrate with Telegram channels to provide enhanced multiplayer gaming experiences. Instead of purely private bot interactions, games can be "linked" to channels where public game information, maps, and broadcasts are shared with all players.

## Core Concept

**Channel-Linked Games**: Games that are associated with a specific Telegram channel where:
- All players are members of the channel
- The bot has posting permissions in the channel
- Public game information is automatically shared
- Players can interact with game content in a social environment

## Primary Channel Features

### 1. **Automated Map Updates** 🗺️

**Trigger Events:**
- New turn begins
- Phase changes (Movement → Retreat → Build)
- After order adjudication
- Manual admin request

**Content:**
- High-resolution game map image
- Current supply center counts per power
- Turn/phase information
- Next deadline countdown

**Message Format:**
```
🗺️ **GAME 42 - SPRING 1902 MOVEMENT PHASE**

Current Supply Centers:
🇦🇹 Austria: 4 centers
🇬🇧 England: 5 centers  
🇫🇷 France: 4 centers
🇩🇪 Germany: 4 centers
🇮🇹 Italy: 3 centers
🇷🇺 Russia: 5 centers
🇹🇷 Turkey: 3 centers

⏰ **Orders due: 2024-03-15 18:00 UTC**
⏳ Time remaining: 23h 45m

[View Details] [Submit Orders] [Game Status]
```

### 2. **Broadcast Message System** 📢

**Message Types:**
- **Public Announcements**: Player-to-all communications
- **Alliance Declarations**: Public alliance formations
- **Diplomatic Statements**: Formal diplomatic positions
- **Press Releases**: In-character diplomatic communications

**Features:**
- Rich formatting with power colors/flags
- Reply threading for discussions
- Reaction voting on proposals
- Message history and search

**Message Format:**
```
📢 **PUBLIC BROADCAST**
🇫🇷 **France** → All Powers

"I propose a Western Triple Alliance between France, England, and Germany 
against the Eastern powers. Who stands with the forces of democracy?"

⏰ Posted: Spring 1902 Movement Phase
💬 Replies: 3 | 👍 2 | 👎 1 | 🤔 4
```

### 3. **Turn & Phase Notifications** ⏰

**Automated Announcements:**
- Turn start notifications
- Phase transition alerts  
- Deadline reminders (24h, 6h, 1h, 15min)
- Order submission confirmations
- Adjudication completion

**Notification Format:**
```
⏰ **DEADLINE APPROACHING - GAME 42**

🚨 **1 HOUR REMAINING** 🚨
Phase: Spring 1902 Movement
Deadline: 2024-03-15 18:00 UTC

Order Status:
✅ Austria, England, France, Russia
⏳ Germany, Italy (processing...)
❌ Turkey (no orders submitted)

@TurkeyPlayer - Your orders are needed!
```

### 4. **Battle Results & Adjudication** ⚔️

**Post-Adjudication Summary:**
- Movement results with visual indicators
- Successful attacks, bounces, support
- Unit builds/disbands
- Supply center changes
- Strategic implications

**Results Format:**
```
⚔️ **ADJUDICATION RESULTS - SPRING 1902**

🎯 **Successful Attacks:**
• A Vienna → Trieste (Italy retreats)
• F North Sea → Norway (Russian retreat)

🔄 **Bounced Movements:**
• A Munich vs A Tyrolia (both hold)
• F English Channel vs F Brest (both hold)

📊 **Supply Center Changes:**
🇦🇹 Austria: +1 (Trieste captured)
🇮🇹 Italy: -1 (Trieste lost)

📈 **Power Rankings:**
1. Russia (5 centers) ↗️
2. England (5 centers) →
3. Austria (4 centers) ↗️
```

## Advanced Channel Features

### 5. **Player Activity Dashboard** 👥

**Real-time Status:**
- Online/offline indicators
- Order submission status
- Last activity timestamps
- Response time analytics

### 6. **Diplomatic Timeline** 📜

**Historical Events:**
- Major battles and outcomes
- Alliance formations/betrayals
- Elimination events
- Key turning points
- Victory progression

### 7. **Supply Center Tracking** 📊

**Visual Progression:**
- Interactive supply center charts
- Historical trends per power
- Victory condition monitoring
- Elimination warnings

### 8. **Strategy Discussion Threads** 💬

**Structured Discussions:**
- Phase-specific discussion threads
- Anonymous strategy polling
- Prediction markets for outcomes
- Post-game analysis discussions

## Channel Management & Administration

### Game-Channel Linking

**Setup Process:**
1. Admin creates/links channel to game
2. Bot joins channel with posting permissions
3. All players must join the channel
4. Channel settings configured
5. Game begins with channel integration active

**Bot Commands for Admins:**
```
/link_channel <game_id> <channel_id>     - Link game to channel
/unlink_channel <game_id>                - Remove channel link
/channel_settings <game_id>              - Configure channel options
/channel_permissions <game_id>           - Manage bot permissions
```

### Channel Settings

**Configurable Options:**
- Auto-post maps (on/off, frequency)
- Broadcast message filtering
- Notification levels (all/important only)
- Player discussion permissions
- Bot response modes
- Historical data retention

### Permission Management

**Required Bot Permissions:**
- Send messages
- Send photos (for maps)
- Pin messages (for important announcements)
- Manage topics/threads (for organized discussions)
- Read message history (for context)

**Channel Admin Controls:**
- Mute specific notification types
- Control player posting permissions
- Moderate diplomatic content
- Archive completed games

## Technical Implementation

### Database Schema Changes

**New Tables:**
```sql
-- Channel linking
CREATE TABLE game_channels (
    game_id INTEGER REFERENCES games(id),
    channel_id BIGINT NOT NULL,
    channel_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settings JSONB DEFAULT '{}',
    PRIMARY KEY (game_id, channel_id)
);

-- Channel message tracking
CREATE TABLE channel_messages (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id),
    channel_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    message_type VARCHAR(50) NOT NULL, -- 'map', 'broadcast', 'notification'
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Player channel membership
CREATE TABLE player_channel_membership (
    user_id BIGINT NOT NULL,
    game_id INTEGER REFERENCES games(id),
    channel_id BIGINT NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    PRIMARY KEY (user_id, game_id, channel_id)
);
```

### API Endpoints

**Channel Management:**
```python
POST /games/{game_id}/channel/link          # Link channel to game
DELETE /games/{game_id}/channel/unlink      # Unlink channel
GET /games/{game_id}/channel/settings       # Get channel settings
PUT /games/{game_id}/channel/settings       # Update channel settings
POST /games/{game_id}/channel/broadcast     # Send broadcast message
```

**Channel Content:**
```python
GET /games/{game_id}/channel/messages       # Get channel message history
POST /games/{game_id}/channel/map           # Post current map
POST /games/{game_id}/channel/status        # Post game status
GET /games/{game_id}/channel/analytics      # Get channel engagement data
```

### Bot Integration Points

**Event Hooks:**
- `on_turn_start()` → Post new turn notification + map
- `on_orders_deadline()` → Post deadline reminders
- `on_adjudication_complete()` → Post battle results + updated map
- `on_phase_change()` → Post phase transition notification
- `on_broadcast_message()` → Forward to channel with formatting
- `on_player_elimination()` → Post elimination announcement
- `on_game_end()` → Post victory announcement + final map

## User Experience Flows

### 1. Setting Up a Channel Game

**For Game Admin:**
1. Create private Telegram channel
2. Add all players to channel
3. Add diplomacy bot to channel
4. Use `/link_channel` command in bot
5. Configure channel settings
6. Start the game

**For Players:**
1. Join the linked channel (required)
2. Register with bot (if not already)
3. Join the game normally through bot
4. Receive channel notifications
5. Participate in channel discussions

### 2. During Gameplay

**Channel Experience:**
- See live map updates after each turn
- Read public broadcasts from other players
- Participate in diplomatic discussions
- Track deadlines and turn progress
- View battle results and analysis

**Private Bot Experience:**
- Submit orders privately to bot
- Send private diplomatic messages
- Manage personal game settings
- Access detailed game statistics

### 3. Post-Game

**Channel Archive:**
- Complete game history preserved
- Final statistics and analysis
- Player achievements and highlights
- Discussion of key moments
- Links to download full game data

## Security & Privacy Considerations

### Information Disclosure

**Public in Channel:**
- Game maps and current positions
- Supply center counts
- Broadcast messages
- Turn/phase information
- Battle results

**Private to Bot Only:**
- Individual player orders
- Private diplomatic messages
- Personal game preferences
- Order submission status (until deadline)

### Channel Security

**Anti-Abuse Measures:**
- Rate limiting on broadcasts
- Message filtering for inappropriate content
- Admin controls for disruptive players
- Automatic moderation of spam
- Ban/kick integration with game removal

### Data Protection

**Privacy Controls:**
- Players can opt-out of specific channel features
- Message retention policies
- Data export capabilities
- Anonymization options for sensitive discussions

## Future Enhancements

### Integration Possibilities

**External Services:**
- Discord bridge for cross-platform play
- Web dashboard for channel viewing
- Mobile app push notifications
- Email digest summaries
- Calendar integration for deadlines

**Advanced Features:**
- AI-powered game analysis and insights
- Automated tournament bracket management
- Spectator mode for non-players
- Live streaming integration
- Replay system with timeline scrubbing

### Analytics & Insights

**Channel Engagement:**
- Message frequency and participation rates
- Player interaction patterns
- Discussion topic analysis
- Strategic trend identification
- Diplomatic relationship mapping

## Implementation Priority

### Phase 1: Core Channel Features
1. Basic channel linking
2. Automated map posting
3. Broadcast message forwarding
4. Turn notifications
5. Simple admin controls

### Phase 2: Enhanced Engagement  
1. Battle results formatting
2. Player status dashboard
3. Discussion threading
4. Reaction-based voting
5. Historical timeline

### Phase 3: Advanced Features
1. Analytics and insights
2. Tournament integration
3. Spectator features
4. Cross-platform bridges
5. AI-powered analysis

## Success Metrics

**Channel Engagement:**
- Messages per game per player
- Channel member retention rate
- Time spent in channel discussions
- Broadcast message engagement rates

**Game Experience:**
- Player satisfaction with channel features
- Completion rate of channel-linked games
- Time to find and join channel games
- Return player rate for channel games

**Technical Performance:**
- Message delivery reliability
- Map generation and posting speed
- API response times for channel features
- Error rates and downtime metrics

---

*This specification provides a comprehensive foundation for implementing rich Telegram channel integration that transforms Diplomacy from a private bot experience into a vibrant, social multiplayer environment.* 