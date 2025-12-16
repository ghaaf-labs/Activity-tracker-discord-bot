import io
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone

import discord
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
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
    conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS voice_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            channel_id INTEGER,
            channel_name TEXT,
            start_time UNIXTIME,
            end_time UNIXTIME
        )
    """)
    conn.commit()
    conn.close()


# Initialize DB on startup
#
# 1. Adapter (Save): datetime -> int (as string)
# Store as integer timestamp string
sqlite3.register_adapter(datetime, lambda dt: str(int(dt.timestamp())))
# 2. Converter (Load): bytes/str -> datetime
# Handle both bytes and string representations
sqlite3.register_converter(
    "UNIXTIME",
    lambda v: datetime.fromtimestamp(
        int(v.decode() if isinstance(v, bytes) else v), tz=timezone.utc
    ),
)
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
init_time: datetime


@bot.event
async def on_ready():
    global init_time
    print(f"Logged in as {bot.user.name}")
    init_time = datetime.now(timezone.utc)
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

    event_time = datetime.now(timezone.utc)

    # CASE 1: User Joined a Channel (before is None, after is a channel)
    # OR User moved from one channel to another (we treat move as leave old + join new)
    if after.channel is not None and (before.channel != after.channel):
        # If they were already being tracked (moving channels), close the old session first
        if member.id in active_sessions:
            await close_session(member, event_time)

        # Start tracking the new session
        active_sessions[member.id] = {
            "start_time": event_time,
            "channel_id": after.channel.id,
            "channel_name": after.channel.name,
        }
        print(f"Started tracking {member.name} in {after.channel.name}")

    # CASE 2: User Left a Channel (before is a channel, after is None)
    elif before.channel is not None and after.channel is None:
        if member.id in active_sessions:
            await close_session(member, event_time)


async def close_session(member, end_time):
    """
    Finalizes a voice session and saves it to the database.
    """
    if member.id not in active_sessions:
        return

    session_data = active_sessions.pop(member.id)
    start_time = session_data["start_time"]
    duration = end_time - start_time

    # Only log sessions that lasted longer than 5 second
    if duration > timedelta(seconds=5):
        conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO voice_sessions (
                user_id, user_name, channel_id, channel_name, start_time, end_time
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                member.id,
                member.name,
                session_data["channel_id"],
                session_data["channel_name"],
                session_data["start_time"],
                end_time,
            ),
        )
        conn.commit()
        conn.close()
        print(f"Logged {member.name}: {duration}s in {session_data['channel_name']}")


def aggregate_durations_by_day(intervals):
    """
    Aggregates a list of (start, end) tuples into a daily dictionary.

    Args:
        intervals: List of tuples [(start_dt, end_dt), ...]

    Returns:
        Dictionary { date_object: timedelta_duration }
    """
    if not intervals:
        return {}

    # 1. Calculate the active durations (same logic as before)
    daily_stats = defaultdict(timedelta)

    # We also need to track the absolute min and max dates to define our range
    min_date = None
    max_date = None

    for start, end in intervals:
        if start > end:
            continue

        # Update global min/max range
        if min_date is None or start.date() < min_date:
            min_date = start.date()
        if max_date is None or end.date() > max_date:
            max_date = end.date()

        # Split intervals across midnights
        current_ptr = start
        while current_ptr.date() < end.date():
            next_midnight = datetime.combine(
                current_ptr.date() + timedelta(days=1), time.min
            )
            daily_stats[current_ptr.date()] += next_midnight - current_ptr
            current_ptr = next_midnight

        daily_stats[current_ptr.date()] += end - current_ptr

    # 2. Fill in the gaps
    # If we have no valid dates found, return empty
    if min_date is None:
        return {}

    current_date = min_date
    final_results = {}

    # Loop through every single day from Start to End
    while current_date <= max_date:
        # Get the duration from our stats, or default to 0 (timedelta())
        duration = daily_stats.get(current_date, timedelta(0))
        final_results[current_date] = duration

        current_date += timedelta(days=1)

    return final_results


def get_daily_stats(user_id, days):
    """
    Retrieves daily aggregated voice time for the specified user over the last N days.
    Returns a list of tuples: [(date, toatal_seconeds), ...]
    """
    conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES)
    c = conn.cursor()

    # Calculate the start date
    end_date = datetime.now(timezone.utc)
    start_datetime = datetime.combine(
        end_date.date() - timedelta(days=days), time.min
    ).replace(tzinfo=timezone.utc)
    start_timestamp = int(start_datetime.timestamp())

    # Query to get daily totals
    c.execute(
        """
        SELECT start_time, end_time
        FROM voice_sessions
        WHERE user_id = ? AND start_time >= ?
        ORDER BY start_time
    """,
        (user_id, start_timestamp),
    )

    results = c.fetchall()
    conn.close()

    return aggregate_durations_by_day(results)


def create_stats_graph(user_name, daily_data, title):
    """
    Creates a bar graph of daily voice chat hours.
    Returns a BytesIO object containing the PNG image.
    """
    if not daily_data:
        return None

    dates = [str(dt) for dt, _ in daily_data]
    hours = [
        td.seconds // 3600 + 60 / ((td.seconds % 3600) // 60) for _, td in daily_data
    ]

    # Create figure and axis
    fig, ax = plt.subplots(figsize=(12, 6))

    # Create bar chart
    bars = ax.bar(dates, hours, color="#5865F2", edgecolor="black", linewidth=0.5)

    # Customize the plot
    ax.set_xlabel("Date", fontsize=12, fontweight="bold")
    ax.set_ylabel("Hours", fontsize=12, fontweight="bold")
    ax.set_title(f"{title} - {user_name}", fontsize=14, fontweight="bold", pad=20)
    ax.grid(axis="y", alpha=0.3, linestyle="--")

    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    plt.xticks(rotation=45, ha="right")

    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{height:.1f}h",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    # Adjust layout to prevent label cutoff
    plt.tight_layout()

    # Save to BytesIO object
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)

    return buf


@bot.command()
async def stats(ctx, days: int = 7, member: discord.Member = None):
    """
    Generates a graph showing daily voice chat hours for the past 7 days.
    Usage: !weekstats [@user] (defaults to yourself if no user mentioned)
    """
    target_user = member or ctx.author

    # Ignore bots
    if target_user.bot:
        await ctx.send("Cannot generate stats for bots!")
        return

    # Get data for the past 7 days
    daily_data = get_daily_stats(target_user.id, days=days).items()
    # Check if there's any data
    total = timedelta(seconds=0)
    for _, time_delta in daily_data:
        total += time_delta

    if total.seconds == 0:
        await ctx.send(
            f"No voice activity recorded for {target_user.display_name} in the past {days} days."
        )
        return

    # Create the graph
    graph_buffer = create_stats_graph(
        target_user.display_name,
        daily_data,
        f"Weekly Voice Chat Hours (Last {days} Days)",
    )

    if graph_buffer:
        file = discord.File(graph_buffer, filename="stats.png")
        await ctx.send(
            f"**{target_user.display_name}** spent **{total.seconds // 3600} hours & {(total.seconds % 3600) // 60} minutes** in voice channels this past **{days}** days.",
            file=file,
        )
    else:
        await ctx.send("Failed to generate graph.")


@bot.command()
async def ping(ctx):
    global init_time
    await ctx.send(
        f"**Pong!** The bot has been online for {datetime.now(timezone.utc) - init_time}."
    )


bot.run(TOKEN)
