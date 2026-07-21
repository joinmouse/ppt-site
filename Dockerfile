FROM python:3.11-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# writable data dir inside the workspace (no root-only paths, no VOLUME)
ENV DATA_DIR=/srv/data DB_PATH=/srv/data/ppt-site.db
RUN mkdir -p /srv/data
# hosting platforms inject $PORT; default to 8000 locally
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
