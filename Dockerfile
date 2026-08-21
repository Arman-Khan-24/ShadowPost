FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-phase1.txt .
RUN pip install --no-cache-dir -r requirements-phase1.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
