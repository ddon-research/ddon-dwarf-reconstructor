FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        binutils \
        ca-certificates \
        elfutils \
        file \
        libdwarf-dev \
        llvm \
        python3 \
        python3-venv \
        zstd \
    && python3 -m venv /opt/toolchain-venv \
    && /opt/toolchain-venv/bin/pip install --no-cache-dir pyelftools==0.31 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/toolchain-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

RUN set -eux; \
    command -v readelf; \
    command -v objdump; \
    command -v llvm-readelf; \
    command -v llvm-dwarfdump; \
    command -v eu-readelf; \
    command -v eu-elflint

WORKDIR /workspace

CMD ["bash", "-lc", "printf '%s\\n' 'binary-toolchain ready'; python3 --version; readelf --version | head -n 1; llvm-readelf --version | head -n 1; eu-readelf --version | head -n 1"]
