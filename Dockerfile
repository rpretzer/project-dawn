FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (git for patch tooling; build tools for wheels if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
      git \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8000

# Default: run realtime chat with a small swarm.
# Override in docker-compose if desired.
CMD ["python3", "launch.py", "--count", "2", "--realtime", "--port", "8000", "--safemode"]

