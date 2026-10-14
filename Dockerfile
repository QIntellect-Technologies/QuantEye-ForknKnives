FROM python:3.10-slim

WORKDIR /app

COPY requirements-cloud.txt .

RUN pip install --no-cache-dir -r requirements-cloud.txt

COPY . .

RUN mkdir -p logs

# Expose port
EXPOSE 5050

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:'+os.environ.get('PORT','5050')+'/health')"

# Run application
CMD ["sh", "-c", "exec gunicorn --worker-class gthread --workers 1 --threads 64 --timeout 0 --bind 0.0.0.0:${PORT:-5050} cloud.app:app"]
