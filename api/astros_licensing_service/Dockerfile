FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py .

ENV ASTROS_LICENSING_PORT=8766
EXPOSE 8766

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8766"]
