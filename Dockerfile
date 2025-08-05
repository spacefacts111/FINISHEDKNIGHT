# Use a slim Python base
FROM python:3.11-slim

# Install system deps for Playwright
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      wget gnupg libnss3 libatk1.0-0 libatk-bridge2.0-0 \
      libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
      libxrandr2 libgbm1 libgtk-3-0 libasound2 && \
    rm -rf /var/lib/apt/lists/*

# Set working dir
WORKDIR /app

# Copy and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install --with-deps chromium

# Copy your bot code and persisted Playwright session
COPY . .

# Default to headless mode; override by setting HEADLESS=false
ENV HEADLESS=true

# Run the bot
CMD ["python", "bot.py"]
