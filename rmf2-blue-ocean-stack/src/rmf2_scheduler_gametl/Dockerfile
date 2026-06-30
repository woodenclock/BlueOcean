ARG BASE_IMAGE=ubuntu:24.04
ARG CC_BUILD_IMAGE=${BASE_IMAGE}
ARG PYTHON_VERSION=3.12

## C++ Builder
FROM ${CC_BUILD_IMAGE} AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ cmake build-essential \
    ca-certificates git \
    libboost-dev \
    libcurl4-openssl-dev \
    libtinyxml2-dev \
    nlohmann-json3-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY ./rmf2_scheduler .

RUN cmake -S . -B build \
      -DCMAKE_BUILD_TYPE=RELEASE \
      -DCMAKE_INSTALL_PREFIX=/app/install \
      -DBUILD_TESTING=OFF && \
    cmake --build build -j"$(nproc)" && \
    cmake --install build


## C++ Runtime Image
FROM ${BASE_IMAGE} AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
  libcurl4 \
  libtinyxml2-10 \
  && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/install/lib /usr/lib
COPY --from=builder /app/install/include /usr/include
COPY --from=builder /app/install/share /usr/share


## Python Builder
FROM builder AS builder-py

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-dev \
    python3-venv \
    pybind11-dev \
    pybind11-json-dev \
  && rm -rf /var/lib/apt/lists/*

ENV CMAKE_PREFIX_PATH=/app/install
ENV LD_LIBRARY_PATH=/app/install/lib
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN python3 -m venv /app/venv
ENV VIRTUAL_ENV=/app/venv
ENV PATH="/app/venv/bin:${PATH}"

WORKDIR /app-py
COPY ./rmf2_scheduler_py .

RUN cmake -S . -B build \
      -DRMF2_SCHEDULER_PY_STANDALONE=ON \
      -DCMAKE_BUILD_TYPE=RELEASE \
      -DCMAKE_INSTALL_PREFIX=/app/venv && \
    cmake --build build -j"$(nproc)" && \
    cmake --install build

WORKDIR /app/stack
COPY pyproject.toml uv.lock ./
COPY blue_ocean_scheduler ./blue_ocean_scheduler
COPY demo_routes ./demo_routes

RUN uv sync --package blue-ocean-scheduler --no-dev --frozen --active --no-editable && \
    python -c "from blue_ocean_scheduler.app import app; print('scheduler import ok')"


## Python Runtime Image
FROM runtime AS server

RUN apt-get update && apt-get install -y --no-install-recommends \
  python3 \
  && rm -rf /var/lib/apt/lists/*

COPY --from=builder-py /app/venv /app/venv
ENV VIRTUAL_ENV=/app/venv
ENV PATH="/app/venv/bin:${PATH}"

EXPOSE 8000
CMD ["blue_ocean_scheduler", "--host", "0.0.0.0", "--port", "8000"]
