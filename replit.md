# Roblox Badge Monitor

## Overview

This is a comprehensive Python-based monitoring application that tracks Roblox user badges and online presence, sending real-time notifications to Discord webhooks. The system features 24/7 operation with multi-group support, parallel monitoring of both badge achievements and online status changes, and includes a keep-alive mechanism for continuous operation on Replit's free tier.

## User Preferences

Preferred communication style: Simple, everyday language.

## How to Use

### Setup Instructions

1. **Configure User IDs**: Open `main.py` and add the Roblox user IDs you want to monitor in the `USER_IDS` list
   ```python
   USER_IDS = [
       123456789,  # Replace with actual Roblox user IDs
       987654321,
   ]
   ```

2. **Configure Discord Webhook**: 
   - Create a webhook in your Discord server
   - Copy the webhook URL and paste it in the `DISCORD_WEBHOOK_URL` variable
   ```python
   DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/your-webhook-url-here"
   ```

3. **Adjust Check Interval** (optional):
   ```python
   CHECK_INTERVAL = 60  # Check every 60 seconds
   ```

4. **Run the Program**: Click the "Run" button or execute `python main.py`

### Discord Message Format

When a new badge is detected, the bot sends a Discord embed containing:
- 🏆 Badge name
- 👤 User name
- 🎮 Game name (if available)
- 🖼️ User avatar thumbnail
- Badge description (if available)

## System Architecture

### Core Components

**Monitoring Engine**
- Polling-based architecture that checks Roblox users at configurable intervals
- Maintains persistent state of known badges in a JSON file (`known_badges.json`)
- Implements pagination handling for Roblox API responses
- Detects new badges by comparing current state with stored state

**Data Storage**
- File-based storage using JSON format (`known_badges.json`)
- Simple key-value structure mapping user IDs to their badge collections
- Persistent across application restarts

**Notification System**
- Discord webhook integration for real-time notifications
- Sends formatted embeds when new badges are detected
- Includes comprehensive badge and user information

**Configuration Management**
- User-configurable settings at the top of the main script
- Supports monitoring multiple Roblox users simultaneously
- Adjustable check intervals for API polling

### API Integration

**Roblox APIs Used**
- `badges.roblox.com/v1/users/{userId}/badges` - Get user badges
- `badges.roblox.com/v1/badges/{badgeId}` - Get badge details
- `games.roblox.com/v1/games?universeIds={universeId}` - Get game information
- `users.roblox.com/v1/users/{userId}` - Get user information
- `thumbnails.roblox.com/v1/users/avatar-headshot` - Get user avatar

### Error Handling

**Graceful Degradation**
- Try-catch blocks around all API calls
- Fallback mechanisms for file I/O operations
- Continues monitoring even if individual API calls fail
- Detailed error logging for debugging

**Rate Limiting Considerations**
- Configurable check intervals to avoid API rate limits
- Sequential processing of users to minimize concurrent requests

## External Dependencies

**Python Libraries**
- `requests` - HTTP communications with APIs
- `json` - Data serialization for badge storage
- `time` - Sleep intervals and timing
- `os` - File system operations
- `datetime` - Timestamp handling for Discord messages

**External Services**
- Roblox APIs for badge and user data
- Discord webhooks for notifications

## 24/7 Operation & Keep-Alive System

### Flask Keep-Alive Server

**Components:**
- `keep_alive.py` - Flask web server for 24/7 operation
- Runs on port 5000 with endpoints:
  - `/` - Returns "Bot de Monitoramento Roblox Ativo! 🏆📶"
  - `/status` - Returns JSON status with uptime info

**How It Works:**
- Flask server runs in a separate daemon thread
- Provides public URL for external monitoring services
- Compatible with UptimeRobot to ping every 5 minutes
- Keeps Replit project active on free tier

### Setting Up 24/7 Operation

**Option 1: UptimeRobot (Free Tier)**
1. Copy your Replit's public URL: `https://[project-name].[username].repl.co`
2. Create free UptimeRobot account
3. Add HTTP monitor pointing to your Replit URL
4. Set check interval to 5 minutes
5. UptimeRobot will ping your server every 5 minutes keeping it active

**Option 2: Replit Deployment (Paid)**
1. Use the configured deployment settings (Reserved VM)
2. Click "Deploy" button in Replit interface
3. Choose Reserved VM for 24/7 operation
4. Bot runs continuously in cloud infrastructure

### Multi-Group Architecture

**Groups Configuration:**
```python
GROUPS = {
    "Group Name": {
        "webhook": "discord_webhook_url",
        "users": [user_id_1, user_id_2]
    }
}
```

**Features:**
- Multiple Discord webhooks for different user groups
- Separate notifications per group
- Independent monitoring per group
- Supports unlimited groups and users

### Recent Changes (Sept 6, 2025)

**Keep-Alive Integration:**
- Added Flask web server for 24/7 operation
- Integrated keep-alive system with main monitoring loop
- Server starts automatically with monitoring systems
- Public URL available for external monitoring services

**Enhanced Monitoring:**
- Parallel badge and presence monitoring using threading
- Real-time online status detection (Offline → Online/In Game/Studio)
- Dual notification system for badges and presence changes
- Persistent state management for both badges and presence