FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 5050
CMD ["sh","-c","gunicorn --bind 0.0.0.0:${PORT:-5050} app:app"]
