FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y build-essential \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get remove -y build-essential && apt-get clean autoclean && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY app ./app

# Create directories for persistent data
RUN mkdir -p /app/db /app/logs

# Set environment variables
ENV VN_MARKET_SERVICE_HOST=0.0.0.0
ENV VN_MARKET_SERVICE_PORT=8765

# Expose port
EXPOSE 8765

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

# Start the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
