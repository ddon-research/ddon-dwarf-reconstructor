FROM python:3.14.7-slim-trixie@sha256:d6e0850f13fda0e2305d4c3c1c2f7930fe1042d34ddd958e49bba6ef685d0bb2

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /bin/

RUN apt-get update \
    && apt-get install --no-install-recommends -y libreoffice-writer groff ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/dwarf-spec-pipeline

COPY pyproject.toml uv.lock README.md .python-version ./
COPY src ./src

RUN uv sync --python 3.14.7 --locked --no-dev

ENTRYPOINT ["/opt/dwarf-spec-pipeline/.venv/bin/dwarf-spec-pipeline"]
