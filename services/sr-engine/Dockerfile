FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY services/sr-engine/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY services/sr-engine /app
COPY shared /app/shared

# Run the service
CMD ["python", "main.py"]

