FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config/ ./config/
COPY ground_station/ ./ground_station/
COPY tests/ ./tests/
RUN useradd --create-home --uid 10001 groundstation \
    && mkdir -p /app/state \
    && chown -R groundstation:groundstation /app
USER groundstation

EXPOSE 9000
CMD ["python", "-m", "ground_station.server", "--host", "0.0.0.0", "--port", "9000"]
