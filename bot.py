import os
import sqlite3
import time
from datetime import datetime

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
TOKEN = os.getenv("DISCORD_TOKEN")
DB_NAME = "stats.db"


# --- Database Setup ---
def init_db():
    """Initializes the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS voice_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            guild_id INTEGER,
            channel_id INTEGER,
            channel_name TEXT,
            start_time REAL,
            end_time REAL,
            duration_seconds REAL,
            date_logged TEXT
        )
    """)
    conn.commit()
    conn.close()


# Initialize DB on startup
init_db()

# --- Bot Setup ---
# Intents are required to track voice states and members
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionary to temporarily store join times: {user_id: start_time}
active_sessions = {}


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    print("Ready to track voice activity...")


@bot.event
async def on_voice_state_update(member, before, after):
    """
    Triggered whenever a member changes their voice state.
    (Joins, leaves, moves, mutes, deafens)
    """

    # Ignore bots to keep data clean
    if member.bot:
        return

    current_time = time.time()

    # CASE 1: User Joined a Channel (before is None, after is a channel)
    # OR User moved from one channel to another (we treat move as leave old + join new)
    if after.channel is not None and (before.channel != after.channel):
        # If they were already being tracked (moving channels), close the old session first
        if member.id in active_sessions:
            await close_session(member, before.channel, current_time)

        # Start tracking the new session
        active_sessions[member.id] = {
            "start_time": current_time,
            "channel_id": after.channel.id,
            "channel_name": after.channel.name,
            "guild_id": after.channel.guild.id,
        }
        print(f"Started tracking {member.name} in {after.channel.name}")

    # CASE 2: User Left a Channel (before is a channel, after is None)
    elif before.channel is not None and after.channel is None:
        if member.id in active_sessions:
            await close_session(member, before.channel, current_time)


async def close_session(member, channel, end_time):
    """
    Finalizes a voice session and saves it to the database.
    """
    if member.id not in active_sessions:
        return

    session_data = active_sessions.pop(member.id)
    start_time = session_data["start_time"]
    duration = end_time - start_time

    # Only log sessions that lasted longer than 1 second
    if duration > 1:
        log_to_db(member, session_data, end_time, duration)
        print(
            f"Logged {member.name}: {int(duration)}s in {session_data['channel_name']}"
        )


def log_to_db(member, session_data, end_time, duration):
    """
    Writes the completed session to SQLite.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute(
        """
        INSERT INTO voice_sessions (
            user_id, username, guild_id, channel_id, channel_name,
            start_time, end_time, duration_seconds, date_logged
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            member.id,
            member.name,
            session_data["guild_id"],
            session_data["channel_id"],
            session_data["channel_name"],
            session_data["start_time"],
            end_time,
            duration,
            date_str,
        ),
    )

    conn.commit()
    conn.close()


# --- Optional: Command to view your own stats ---
@bot.command()
async def mystats(ctx):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Sum total duration for the user requesting the command
    c.execute(
        "SELECT SUM(duration_seconds) FROM voice_sessions WHERE user_id = ?",
        (ctx.author.id,),
    )
    result = c.fetchone()[0]
    conn.close()

    if result:
        hours = round(result / 3600, 2)
        await ctx.send(
            f"Hey {ctx.author.mention}, you have spent a total of **{hours} hours** in voice channels."
        )
    else:
        await ctx.send(
            f"{ctx.author.mention}, I haven't tracked any voice time for you yet."
        )


bot.run(TOKEN)
