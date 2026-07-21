FROM python:3.11-slim
WORKDIR /srv
COPY requirements.txt .
# China-network-friendly: mirror first, official PyPI fallback; retries + longer timeout
RUN pip install --no-cache-dir --retries 5 --timeout 120 \
      -i https://mirrors.aliyun.com/pypi/simple/ \
      -r requirements.txt \
 || pip install --no-cache-dir --retries 5 --timeout 120 -r requirements.txt
COPY app ./app
ENV DATA_DIR=/srv/data DB_PATH=/srv/data/ppt-site.db
RUN mkdir -p /srv/data
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
