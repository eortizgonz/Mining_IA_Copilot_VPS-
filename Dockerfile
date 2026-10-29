FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5050

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .

USER app
EXPOSE 5050

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','5050')+'/login',timeout=3)" || exit 1

CMD ["sh","-c","exec gunicorn --bind 0.0.0.0:${PORT:-5050} --workers ${GUNICORN_WORKERS:-2} --threads ${GUNICORN_THREADS:-4} --timeout ${GUNICORN_TIMEOUT:-60} --access-logfile - --error-logfile - app:app"]
