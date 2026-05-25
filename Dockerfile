FROM python:3.11-slim

# Install system dependencies required for PostgreSQL and Kafka C-libraries
RUN apt-get update && apt-get install -y \
    gcc \
    librdkafka-dev \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

ENV PYTHONPATH=/app

CMD ["uvicorn", "src.apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
