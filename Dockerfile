FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements-online.txt ./
RUN pip install --no-cache-dir -r requirements-online.txt
COPY . .
ENV PORT=8080
CMD ["sh", "-c", "gunicorn --workers ${WEB_CONCURRENCY:-3} --threads 4 --bind 0.0.0.0:${PORT:-8080} --timeout 120 wsgi:app"]
