# Discord Voice Activity Tracker Bot

A Discord bot that tracks voice channel activity and generates statistical graphs for users and servers.

## Features

- **Automatic Voice Tracking**: Monitors when users join, leave, or switch voice channels
- **Activity Statistics**: Generate personal activity graphs with `!stats`
- **Weekly Server Overview**: View server-wide activity with `!weekly`
 Commands
 
## Setup

### Prerequisites

- Python 3.11 or higher
- Discord Bot Token ([How to create a bot](https://discord.com/developers/applications))

### Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd discord_bot
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirments.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
```

Edit `.env` and add your Discord bot token:
```
DISCORD_TOKEN=your_discord_bot_token_here
```

5. Run the bot:
```bash
python bot.py
```
