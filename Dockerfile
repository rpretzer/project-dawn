FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directory
RUN mkdir -p /data

# Create non-root user
RUN useradd -m -u 1000 dawn && \
    chown -R dawn:dawn /app /data

USER dawn

# Expose ports
EXPOSE 8000 8080 9090

# Run application
CMD ["python", "-m", "server_p2p"]
