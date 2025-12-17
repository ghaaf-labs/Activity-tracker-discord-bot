import os
import re
import signal
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import get_daily_user_stats, init_db, save_voice_session
from graphs import create_activity_per_day_graph, create_grouped_bar_chart

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
TOKEN = os.getenv("DISCORD_TOKEN")
MIN_TIME_TRACK = 2  # in seconds

# --- Database Setup ---
init_db()

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True
intents.guilds = True


bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionary to temporarily store join times: {user_id: start_time}
active_users = {}
init_time: datetime


@dataclass
class UserVoiceEvent:
    user_id: int
    user_name: str
    channel_id: int
    channel_name: str
    timestamp: datetime


def clean_exit(signum, frame):
    for event in active_users.values():
        end_time = datetime.now(timezone.utc)
        save_voice_session(
            event.user_id,
            event.user_name,
            event.channel_id,
            event.channel_name,
            event.timestamp,
            end_time,
        )
        print(f"Tracked user {event.user_name} in {event.channel_name}")
    sys.exit(0)


# register_signals logic
# SIGINT = Ctrl+C
# SIGTERM = Docker stop / System kill
signal.signal(signal.SIGINT, clean_exit)
signal.signal(signal.SIGTERM, clean_exit)


@bot.event
async def on_ready():
    global init_time
    print(f"Logged in as {bot.user.name}")
    init_time = datetime.now(timezone.utc)
    # 1. Loop through every Guild (Server) the bot is in
    for guild in bot.guilds:
        # 2. Loop through every Voice Channel in that Guild
        for channel in guild.voice_channels:
            # 3. Loop through every Member currently in that Channel
            for member in channel.members:
                print(f"Found active user: {member.name} in {channel.name}")
                active_users[member.id] = UserVoiceEvent(
                    user_id=member.id,
                    user_name=member.name,
                    channel_id=channel.id,
                    channel_name=channel.name,
                    timestamp=datetime.now(timezone.utc),
                )


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
        if member.id in active_users:
            await log_user(active_users.pop(member.id))

        # Start tracking the new session
        active_users[member.id] = UserVoiceEvent(
            user_id=member.id,
            user_name=member.name,
            channel_id=after.channel.id,
            channel_name=after.channel.name,
            timestamp=event_time,
        )
        print(f"Started tracking {member.name} in {after.channel.name}")

    # CASE 2: User Left a Channel (before is a channel, after is None)
    elif before.channel is not None and after.channel is None:
        if member.id in active_users:
            await log_user(active_users.pop(member.id))


async def log_user(user: UserVoiceEvent):
    """
    Finalizes a voice session and saves it to the database.
    """
    end_time = datetime.now(timezone.utc)
    duration = end_time - user.timestamp

    # Only log sessions that lasted longer than 5 seconds
    if duration > timedelta(seconds=MIN_TIME_TRACK):
        save_voice_session(
            user_id=user.user_id,
            user_name=user.user_name,
            channel_id=user.channel_id,
            channel_name=user.channel_name,
            start_time=user.timestamp,
            end_time=end_time,
        )
        print(f"Logged {user.user_name} for {duration} in {user.channel_name}")
    else:
        print(f"Active time for {user.user_name} is less than {MIN_TIME_TRACK}s")


@bot.command()
async def weekly(ctx):
    """
    Generates a graph showing weekly voice chat activity for all members.
    Usage: !stats [@user] (defaults to yourself if not specified)
    """

    # get this week
    now = datetime.now()
    form_date = datetime.combine(
        (now - timedelta(days=now.weekday())).date(), datetime.min.time()
    )
    to_date = datetime.combine(
        (now + timedelta(days=6 - now.weekday())).date(), datetime.max.time()
    )

    user_activity = {}
    days = None
    for user in ctx.guild.members:
        if not user.bot:
            dates, values = zip(
                *list(get_daily_user_stats(user.id, form_date, to_date))
            )
            user_activity[user.display_name] = [
                v.total_seconds() / 3600 for v in values
            ]
            if not days:
                days = (day.strftime("%a\n%m%d") for day in dates)

    # Create the graph
    graph_buffer = create_grouped_bar_chart(days, user_activity)

    if graph_buffer:
        file = discord.File(graph_buffer, filename="week_stats.png")
        await ctx.send(
            "Weekly server activity.",
            file=file,
        )
    else:
        await ctx.send("Failed to generate graph.")


@bot.command()
async def stats(ctx, target_user: discord.Member | None = None):
    """
    Generates a graph showing daily voice chat hours for the past 7 days.
    """
    if not target_user:
        target_user = ctx.author
    days = 7

    # Ignore bots
    if target_user.bot:
        await ctx.send("Cannot generate stats for bots!")
        return

    # Get data for the specified number of days
    form_date = datetime.combine(
        datetime.now().date() - timedelta(days=days), datetime.min.time()
    )
    to_date = datetime.combine(datetime.now().date(), datetime.max.time())
    daily_data = get_daily_user_stats(target_user.id, form_date, to_date)

    # Calculate total time
    total = timedelta(seconds=0)
    for _, time_delta in daily_data:
        total += time_delta

    if total.seconds == 0:
        await ctx.send(
            f"No voice activity recorded for {target_user.display_name} in last {days} days."
        )
        return

    # Create the graph
    graph_buffer = create_activity_per_day_graph(daily_data)

    if graph_buffer:
        file = discord.File(graph_buffer, filename="stats.png")
        await ctx.send(
            f"**{target_user.display_name}** was active for **{total.seconds // 3600}h {(total.seconds % 3600) // 60}m** in last **{days}** days.",
            file=file,
        )
    else:
        await ctx.send("Failed to generate graph.")


@bot.command()
async def ping(ctx):
    """
    Shows bot uptime.
    Usage: !ping
    """
    global init_time
    await ctx.send(
        f"**Pong!** The bot has been online for {datetime.now(timezone.utc) - init_time}."
    )


if __name__ == "__main__":
    bot.run(TOKEN)
