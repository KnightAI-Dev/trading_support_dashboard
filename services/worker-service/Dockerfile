FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY services/worker-service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY services/worker-service /app
COPY shared /app/shared
COPY services/swing-engine /app/swing-engine
COPY services/sr-engine /app/sr-engine
COPY services/fib-entry-engine /app/fib-entry-engine
COPY services/confluence-engine /app/confluence-engine
COPY services/risk-engine /app/risk-engine

# Run Celery worker
CMD ["celery", "-A", "main", "worker", "--loglevel=info"]

