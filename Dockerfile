FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install . \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app

USER app

EXPOSE 8000

ENTRYPOINT ["clinical-trials-mcp", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
