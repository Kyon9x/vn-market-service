FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y build-essential \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get remove -y build-essential && apt-get clean autoclean && rm -rf /var/lib/apt/lists/*

COPY app ./app

ENV VN_MARKET_SERVICE_HOST=0.0.0.0
ENV VN_MARKET_SERVICE_PORT=8765

EXPOSE 8765

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
