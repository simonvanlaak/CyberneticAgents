FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md MANIFEST.in ./
COPY src ./src
COPY scripts ./scripts
COPY main.py ./

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e .

RUN mkdir -p /app/data /app/logs

CMD ["python", "-m", "src.cyberagent.cli.cyberagent", "serve"]
