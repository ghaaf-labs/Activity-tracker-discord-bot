import io

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
# from PIL import Image


def create_activity_per_day_graph(daily_data):
    """
    Creates a bar graph of daily voice chat hours.

    Args:
        daily_data: Iterable of (date, timedelta) tuples

    Returns:
        BytesIO object containing the PNG image, or None if no data
    """
    if not daily_data:
        return None

    # Convert data to lists
    dates, hours = zip(
        *[
            (date.strftime("%a\n%m/%d"), (total.total_seconds() / 3600))
            for date, total in daily_data
        ]
    )

    # Create bar chart
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(dates, hours, color="#5865F2")

    # Labels and title
    ax.set_xlabel("Date")
    ax.set_ylabel("Hours")
    ax.set_title("User voice chat activity per day")
    ax.grid(axis="y", alpha=0.3)

    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height,
                f"{int(height)}h {int((height - int(height)) * 60)}m",
                ha="center",
                va="bottom",
            )

    plt.xticks(rotation=0)
    plt.tight_layout()

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=250)
    buf.seek(0)
    plt.close(fig)

    return buf


def create_grouped_bar_chart(dates, user_data):
    """
    Creates a grouped bar chart with multiple users.

    Args:
        dates: List of date strings for x-axis
        user_data: Dict where keys are usernames and values are lists of hours
                   Example: {"Alice": [2.5, 3.0, 1.5], "Bob": [1.0, 2.0, 3.5]}

    Returns:
        BytesIO object containing the PNG image, or None if no data
    """
    dates = list(dates)

    if not dates or not user_data:
        return None

    num_users = len(user_data)
    x = np.arange(len(dates))
    width = 0.8 / num_users

    fig, ax = plt.subplots(figsize=(10, 6))

    for i, (username, hours) in enumerate(user_data.items()):
        offset = width * (i - num_users / 2 + 0.5)
        ax.bar(x + offset, hours, width, label=username)

    ax.set_xlabel("Date")
    ax.set_ylabel("Hours")
    ax.set_title("User Activity")
    ax.set_xticks(x)
    ax.set_xticklabels(dates, rotation=0)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=250)
    buf.seek(0)
    plt.close(fig)

    return buf


def create_daily_activity(data):

    df = pd.DataFrame(data)

    # 1. Assign a dummy date to the time strings so Plotly can parse them as datetime objects
    # dummy_date = "2024-01-01 "
    # df["Start"] = pd.to_datetime(dummy_date + df["Start"])
    # df["End"] = pd.to_datetime(dummy_date + df["End"])

    # 2. Create the timeline
    fig = px.timeline(
        df,
        x_start="start",
        x_end="end",
        y="user",
        color="channel",
        title="User Activity (24-Hour View)",
    )

    # 3. Format the X-axis to show ONLY time
    fig.update_xaxes(
        tickformat="%H:%M",
        # Optional: Force the range to be the full 24 hours
        # range=[dummy_date + "00:00:00", dummy_date + "23:59:59"],
        dtick=3600000 * 2,  # Show a tick every 2 hours (ms * seconds * hours)
    )
    fig.update_yaxes(autorange="reversed")  # Traditional Gantt view (top to bottom)

    buf = io.BytesIO()
    # 3. Write the image to the buffer
    #    - file: accepts the buffer object
    #    - format: 'png', 'jpeg', 'svg', or 'pdf'
    #    - scale: equivalent to increasing DPI (default is 1, 2-3 is usually high res)
    fig.write_image(buf, format="png", width=800, height=400, scale=2)
    buf.seek(0)

    # img = Image.open(buf)
    # img.show()
    # fig.show()

    return buf
