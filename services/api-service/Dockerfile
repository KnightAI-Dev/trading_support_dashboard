FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY services/api-service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY services/api-service /app
COPY shared /app/shared

# Run the service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

