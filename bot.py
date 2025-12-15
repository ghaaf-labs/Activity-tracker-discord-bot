import io
import os
import sqlite3
import time
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

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


def get_daily_stats(user_id, days):
    """
    Retrieves daily aggregated voice time for the specified user over the last N days.
    Returns a list of tuples: [(date, hours), ...]
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Calculate the start date
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # Query to get daily totals
    c.execute("""
        SELECT
            DATE(date_logged) as day,
            SUM(duration_seconds) / 3600.0 as hours
        FROM voice_sessions
        WHERE user_id = ? AND date_logged >= ?
        GROUP BY DATE(date_logged)
        ORDER BY day
    """, (user_id, start_date.strftime("%Y-%m-%d")))

    results = c.fetchall()
    conn.close()

    # Create a complete date range with 0 hours for missing days
    daily_data = {}
    for row in results:
        daily_data[row[0]] = row[1]

    # Fill in missing days with 0 hours
    complete_data = []
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        hours = daily_data.get(date_str, 0)
        complete_data.append((current_date, hours))
        current_date += timedelta(days=1)

    return complete_data


def create_stats_graph(user_name, daily_data, title):
    """
    Creates a bar graph of daily voice chat hours.
    Returns a BytesIO object containing the PNG image.
    """
    if not daily_data:
        return None

    dates = [item[0] for item in daily_data]
    hours = [item[1] for item in daily_data]

    # Create figure and axis
    fig, ax = plt.subplots(figsize=(12, 6))

    # Create bar chart
    bars = ax.bar(dates, hours, color='#5865F2', edgecolor='black', linewidth=0.5)

    # Customize the plot
    ax.set_xlabel('Date', fontsize=12, fontweight='bold')
    ax.set_ylabel('Hours', fontsize=12, fontweight='bold')
    ax.set_title(f'{title} - {user_name}', fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    plt.xticks(rotation=45, ha='right')

    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}h',
                   ha='center', va='bottom', fontsize=8)

    # Adjust layout to prevent label cutoff
    plt.tight_layout()

    # Save to BytesIO object
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf


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


@bot.command()
async def weekstats(ctx, member: discord.Member = None):
    """
    Generates a graph showing daily voice chat hours for the past 7 days.
    Usage: !weekstats [@user] (defaults to yourself if no user mentioned)
    """
    target_user = member or ctx.author

    # Ignore bots
    if target_user.bot:
        await ctx.send("Cannot generate stats for bots!")
        return

    await ctx.send(f"Generating weekly stats for {target_user.display_name}...")

    # Get data for the past 7 days
    daily_data = get_daily_stats(target_user.id, days=7)

    # Check if there's any data
    total_hours = sum(hours for _, hours in daily_data)
    if total_hours == 0:
        await ctx.send(f"No voice activity recorded for {target_user.display_name} in the past 7 days.")
        return

    # Create the graph
    graph_buffer = create_stats_graph(
        target_user.display_name,
        daily_data,
        "Weekly Voice Chat Hours (Last 7 Days)"
    )

    if graph_buffer:
        file = discord.File(graph_buffer, filename="weekstats.png")
        await ctx.send(
            f"**{target_user.display_name}** spent **{total_hours:.2f} hours** in voice channels this week!",
            file=file
        )
    else:
        await ctx.send("Failed to generate graph.")


@bot.command()
async def monthstats(ctx, member: discord.Member = None):
    """
    Generates a graph showing daily voice chat hours for the past 30 days.
    Usage: !monthstats [@user] (defaults to yourself if no user mentioned)
    """
    target_user = member or ctx.author

    # Ignore bots
    if target_user.bot:
        await ctx.send("Cannot generate stats for bots!")
        return

    await ctx.send(f"Generating monthly stats for {target_user.display_name}...")

    # Get data for the past 30 days
    daily_data = get_daily_stats(target_user.id, days=30)

    # Check if there's any data
    total_hours = sum(hours for _, hours in daily_data)
    if total_hours == 0:
        await ctx.send(f"No voice activity recorded for {target_user.display_name} in the past 30 days.")
        return

    # Create the graph
    graph_buffer = create_stats_graph(
        target_user.display_name,
        daily_data,
        "Monthly Voice Chat Hours (Last 30 Days)"
    )

    if graph_buffer:
        file = discord.File(graph_buffer, filename="monthstats.png")
        await ctx.send(
            f"**{target_user.display_name}** spent **{total_hours:.2f} hours** in voice channels this month!",
            file=file
        )
    else:
        await ctx.send("Failed to generate graph.")


bot.run(TOKEN)
