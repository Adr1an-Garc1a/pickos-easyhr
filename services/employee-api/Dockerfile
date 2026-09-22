FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Cloud Run inyecta la variable PORT; gunicorn la respeta con $PORT
ENV PORT=8080
EXPOSE 8080
USER 1000
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 0 app:app
