# Package the reviewed Python application and synthetic fixtures, never local secrets or run state.
# The non-root container runs one FastAPI process; cloud services remain separately configured.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    LAB_DATA_DIR=/app/artifacts/local \
    LAB_CORPUS_PATH=/app/corpus/web_knowledge.json

WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
COPY requirements.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps .
COPY corpus/ ./corpus/
COPY scenarios/ ./scenarios/
COPY scripts/container_smoke.py ./container_smoke.py
RUN mkdir -p /app/artifacts && chown -R 10001:10001 /app/artifacts
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)" || exit 1
CMD ["python", "-m", "aws_agent_platform_lab.web"]
