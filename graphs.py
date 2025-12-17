import io

import matplotlib.pyplot as plt


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
            (date.strftime("%m/%d %a"), (total.total_seconds() / 3600))
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

    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300)
    buf.seek(0)
    plt.close(fig)

    return buf


def create_multi_user_barchart(user_daily_data):
    """
    Creates a grouped bar chart showing voice chat hours for multiple users across multiple days.

    Args:
        user_daily_data: Dictionary mapping username to list of (date, timedelta) tuples
                        e.g., {
                            "User1": [(date1, timedelta1), (date2, timedelta2)],
                            "User2": [(date1, timedelta1), (date2, timedelta2)]
                        }

    Returns:
        BytesIO object containing the PNG image, or None if no data
    """
    if not user_daily_data:
        return None

    # Define colors for different users
    colors = [
        "#5865F2",
        "#57F287",
        "#FEE75C",
        "#EB459E",
        "#ED4245",
        "#5BCEFA",
        "#F26522",
    ]

    # Extract all unique dates and sort them
    all_dates = set()
    for daily_data in user_daily_data.values():
        for date, _ in daily_data:
            all_dates.add(date)

    sorted_dates = sorted(all_dates)
    date_labels = [date.strftime("%m/%d %a") for date in sorted_dates]

    # Prepare data for each user
    user_hours = {}
    for username, daily_data in user_daily_data.items():
        hours_dict = {date: total.total_seconds() / 3600 for date, total in daily_data}
        user_hours[username] = [hours_dict.get(date, 0) for date in sorted_dates]

    # Create grouped bar chart
    fig, ax = plt.subplots(figsize=(12, 6))

    num_users = len(user_hours)
    num_dates = len(sorted_dates)
    bar_width = 0.8 / num_users
    x = range(num_dates)

    # Plot bars for each user
    for i, (username, hours) in enumerate(user_hours.items()):
        offset = (i - num_users / 2 + 0.5) * bar_width
        bars = ax.bar(
            [pos + offset for pos in x],
            hours,
            bar_width,
            label=username,
            color=colors[i % len(colors)],
        )

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
                    fontsize=8,
                )

    # Labels and title
    ax.set_xlabel("Date")
    ax.set_ylabel("Hours")
    ax.set_title("Voice chat activity comparison across users")
    ax.set_xticks(x)
    ax.set_xticklabels(date_labels, rotation=45, ha="right")
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300)
    buf.seek(0)
    plt.close(fig)

    return buf
