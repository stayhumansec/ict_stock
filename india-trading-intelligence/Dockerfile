FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY backtest/ backtest/
COPY live/ live/
COPY scripts/ scripts/

# Shared SQLite file lives here - mount a volume at /data to persist it
# across container restarts/rebuilds.
ENV SMC_DB_PATH=/data/smc.db
VOLUME ["/data"]
