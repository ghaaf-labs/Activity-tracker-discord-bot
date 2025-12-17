# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if needed for matplotlib/pillow)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirments.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirments.txt

# Copy application files
COPY *.py .

# Create directory for SQLite database
RUN mkdir -p /app/data

# Set environment variable for database location (optional)
ENV DISCORD_TOKEN=your_discord_bot_token_here

# Run the bot
CMD ["python", "bot.py"]
