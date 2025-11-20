FROM python:3.10-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for numpy/scikit-learn/chromadb, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/api/requirements.txt services/api/requirements.txt
COPY services/ui/requirements.txt services/ui/requirements.txt
RUN pip install --no-cache-dir -r services/api/requirements.txt \
 && pip install --no-cache-dir -r services/ui/requirements.txt

COPY . .

RUN chmod +x docker-entrypoint.sh

EXPOSE 8090 8502

ENV API_PORT=8090 \
    UI_PORT=8502 \
    OLLAMA_URL=http://host.docker.internal:11434

ENTRYPOINT ["./docker-entrypoint.sh"]
