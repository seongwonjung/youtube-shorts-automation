FROM python:3.12-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY channels/ channels/
COPY run.py .

VOLUME ["/app/runs", "/app/cache", "/app/secrets"]

ENTRYPOINT ["uv", "run", "python", "run.py"]
