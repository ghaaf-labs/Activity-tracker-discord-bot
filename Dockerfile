FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (if needed for matplotlib/pillow)
RUN apt-get update && apt-get install -y \
    gcc libnss3 libatk-bridge2.0-0 libcups2 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirments.txt .

RUN pip install --no-cache-dir -r requirments.txt

# some how drowing graph library needs chrome
RUN plotly_get_chrome -y

# Copy application files
COPY *.py .

# Set environment variable for database location (optional)
ENV DISCORD_TOKEN=your_discord_bot_token_here

CMD ["python", "bot.py"]
