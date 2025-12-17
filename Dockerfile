FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (if needed for matplotlib/pillow)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirments.txt .

RUN pip install --no-cache-dir -r requirments.txt

# Copy application files
COPY *.py .

# Set environment variable for database location (optional)
ENV DISCORD_TOKEN=your_discord_bot_token_here

CMD ["python", "bot.py"]
