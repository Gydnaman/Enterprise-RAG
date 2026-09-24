FROM python:3.13.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/api/src
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.10
COPY apps/api /app/apps/api
RUN uv sync --project apps/api --locked --no-dev
RUN mkdir -p /app/data/uploads
EXPOSE 8000
CMD ["uv", "run", "--project", "apps/api", "uvicorn", "rag_workbench.main:app", "--app-dir", "apps/api/src", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
