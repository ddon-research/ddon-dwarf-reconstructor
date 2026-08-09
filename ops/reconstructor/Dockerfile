# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.14.7-slim-trixie@sha256:d6e0850f13fda0e2305d4c3c1c2f7930fe1042d34ddd958e49bba6ef685d0bb2

FROM ${PYTHON_IMAGE} AS python-runtime
FROM ghcr.io/astral-sh/uv:0.12.3@sha256:dfd1e6972e100ca2fbf1f391effc3dd4aa57f319bf03c3e321e0a3f3341ed5af AS uv-runtime

FROM python-runtime

ARG DDON_UID=1000
ARG DDON_GID=1000

COPY --from=uv-runtime /uv /uvx /bin/

ENV DEBIAN_FRONTEND=noninteractive \
    GIT_CONFIG_COUNT=1 \
    GIT_CONFIG_KEY_0=safe.directory \
    GIT_CONFIG_VALUE_0=/workspace \
    HOME=/home/ddon \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PATH=/opt/venv/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

RUN apt-get update \
    && apt-get install --no-install-recommends --yes ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid "${DDON_GID}" ddon \
    && useradd --create-home --gid "${DDON_GID}" --uid "${DDON_UID}" --shell /usr/sbin/nologin ddon

WORKDIR /workspace

COPY pyproject.toml uv.lock README.md .python-version ./

RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --locked --no-dev --group test --group performance --no-install-project

COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --locked --no-dev --group test --group performance \
    && mkdir --parents /artifacts /inputs /workspace/logs /workspace/output \
    && chown --recursive ddon:ddon /artifacts /inputs /opt/venv /workspace

ENV UV_CACHE_DIR=/artifacts/uv-cache \
    UV_NO_SYNC=1

USER ddon

ENTRYPOINT ["uv", "run", "--no-sync", "ddon-dwarf-reconstructor"]
CMD ["--help"]
