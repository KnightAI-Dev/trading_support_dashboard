FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY services/ingestion-service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY services/ingestion-service /app
COPY shared /app/shared

# Run the service
CMD ["python", "main.py"]

