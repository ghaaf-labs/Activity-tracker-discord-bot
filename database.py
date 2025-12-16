import sqlite3
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone

DB_NAME = "stats.db"


def init_db():
    """Initializes the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS voice_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            channel_id INTEGER,
            channel_name TEXT,
            start_time INTEGER,
            end_time INTEGER
        )
    """)
    conn.commit()
    conn.close()


def setup_sqlite_adapters():
    """Register SQLite adapters and converters for datetime objects."""
    # Adapter (Save): datetime -> int
    sqlite3.register_adapter(datetime, lambda dt: int(dt.timestamp()))
    # Converter (Load): int -> datetime
    sqlite3.register_converter(
        "timestamp",
        lambda v: datetime.fromtimestamp(int(v), tz=timezone.utc),
    )


def save_voice_session(
    user_id: int, user_name: str,
    channel_id: int, channel_name: str,
    start_time: datetime, end_time: datetime
):
    """
    Saves a voice session to the database.

    Args:
        user_id: Discord user ID
        user_name: Discord username
        channel_id: Voice channel ID
        channel_name: Voice channel name
        start_time: Session start datetime
        end_time: Session end datetime
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO voice_sessions (
            user_id, user_name, channel_id, channel_name, start_time, end_time
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            user_name,
            channel_id,
            channel_name,
            int(start_time.timestamp()),
            int(end_time.timestamp()),
        ),
    )
    conn.commit()
    conn.close()


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

    daily_stats = defaultdict(timedelta)
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

    # Fill in the gaps
    if min_date is None:
        return {}

    current_date = min_date
    final_results = {}

    while current_date <= max_date:
        duration = daily_stats.get(current_date, timedelta(0))
        final_results[current_date] = duration
        current_date += timedelta(days=1)

    return final_results


def get_daily_stats(user_id, days):
    """
    Retrieves daily aggregated voice time for the specified user over the last N days.

    Args:
        user_id: Discord user ID
        days: Number of days to look back

    Returns:
        Dictionary of {date: timedelta} for each day in the range
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Calculate the start date
    end_date = datetime.now(timezone.utc)
    start_datetime = datetime.combine(
        end_date.date() - timedelta(days=days), time.min
    ).replace(tzinfo=timezone.utc)
    start_timestamp = int(start_datetime.timestamp())

    # Query to get sessions
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

    # Convert integer timestamps back to datetime objects
    datetime_results = [
        (
            datetime.fromtimestamp(start, tz=timezone.utc),
            datetime.fromtimestamp(end, tz=timezone.utc),
        )
        for start, end in results
    ]

    return aggregate_durations_by_day(datetime_results)
