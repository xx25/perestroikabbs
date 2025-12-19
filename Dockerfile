FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    default-libmysqlclient-dev \
    pkg-config \
    lrzsz \
    ckermit \
    bc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create BBS user and directories
RUN useradd -m -s /bin/bash bbs && \
    mkdir -p /var/lib/bbs/files /var/lib/bbs/uploads /var/log/bbs && \
    chown -R bbs:bbs /var/lib/bbs /var/log/bbs

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=bbs:bbs . .

# Create necessary directories
RUN mkdir -p /app/bbs/app/assets/ansi && \
    chown -R bbs:bbs /app

# Expose telnet port
EXPOSE 2323

# Switch to non-root user
USER bbs

# Entry point
CMD ["python", "-m", "bbs.app.main"]