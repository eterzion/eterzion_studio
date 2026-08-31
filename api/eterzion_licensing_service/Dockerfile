FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ETERZION_LICENSING_PORT=8766

WORKDIR /app

RUN groupadd --gid 10001 eterzion \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin eterzion

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 run.py ./

USER 10001:10001
EXPOSE 8766

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8766/health', timeout=2)"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8766"]
