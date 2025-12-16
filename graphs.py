import io

import matplotlib.dates as mdates
import matplotlib.pyplot as plt


def create_stats_graph(user_name, daily_data, title):
    """
    Creates a bar graph of daily voice chat hours.

    Args:
        user_name: Display name of the user
        daily_data: Iterable of (date, timedelta) tuples
        title: Title for the graph

    Returns:
        BytesIO object containing the PNG image, or None if no data
    """
    if not daily_data:
        return None

    dates = [str(dt) for dt, _ in daily_data]
    hours = [td.total_seconds() / 3600 for _, td in daily_data]

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
