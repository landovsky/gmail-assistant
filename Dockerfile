FROM python:3.12-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies into a virtual env (cached layer)
COPY pyproject.toml .
RUN uv venv /app/.venv && uv pip install --python /app/.venv/bin/python -e "."

# --- Runtime stage ---
FROM python:3.12-slim

WORKDIR /app

# Copy virtual env from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY src/ src/
COPY config/ config/
COPY pyproject.toml .

# Create data and logs directories
RUN mkdir -p data logs

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
