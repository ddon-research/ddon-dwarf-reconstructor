FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /uvx /bin/

RUN apt-get update \
    && apt-get install --no-install-recommends -y libreoffice-writer groff ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/dwarf-spec-pipeline

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev

ENTRYPOINT ["/opt/dwarf-spec-pipeline/.venv/bin/dwarf-spec-pipeline"]
