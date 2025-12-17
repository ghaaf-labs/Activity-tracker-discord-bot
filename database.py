import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone

DB_NAME = "./data/stats.db"


def init_db():
    """Initializes the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # start_time and end_time are unix timestamps
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


def save_voice_session(
    user_id: int,
    user_name: str,
    channel_id: int,
    channel_name: str,
    start_time: datetime,
    end_time: datetime,
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


def get_daily_user_stats(user_id: int, from_date: datetime, to_date: datetime):
    """
    Retrieves daily aggregated voice time per day for the specified user.

    Args:
        user_id: Discord user ID
        from_date: Filter in the date range
        to_date: Filter in the date range

    Returns:
        list of (date, timedelta) for the user
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Query to get sessions
    c.execute(
        """
        SELECT start_time, end_time
        FROM voice_sessions
        WHERE user_id = ? AND start_time >= ? AND end_time <= ?
        ORDER BY start_time
    """,
        (user_id, int(from_date.timestamp()), int(to_date.timestamp())),
    )

    results = c.fetchall()
    conn.close()

    # Create a list of (date, timedelta) for hours per day
    # time per day can go more than 24h if the underlying data is incorect (this is intended behavior)
    time_per_date = defaultdict(timedelta)
    for start_ts, end_ts in results:
        start = datetime.fromtimestamp(start_ts, timezone.utc)
        end = datetime.fromtimestamp(end_ts, timezone.utc)
        if start.date() == end.date():
            time_per_date[start.date()] += end - start
        else:  # start and end are not in the same day
            midnight = datetime.combine(
                start.date() + timedelta(days=1), datetime.min.time()
            )
            time_per_date[start.date()] += midnight - start
            # they maybe more than one day apart so this is safer than using previous midnight
            midnight = datetime.combine(
                end.date() - timedelta(days=1), datetime.max.time()
            )
            time_per_date[start.date()] += end - midnight
            # if they are more than one day apart
            for i in range(1, (end - start).days):
                time_per_date[start.date() + timedelta(days=i)] += timedelta(days=1)

    # zero pad the missing days
    date_cursor = from_date.date()
    targetdate = to_date.date()
    while date_cursor <= targetdate:
        if not time_per_date[date_cursor]:
            time_per_date[date_cursor] = timedelta(seconds=0)
        date_cursor += timedelta(days=1)

    return sorted(time_per_date.items())
