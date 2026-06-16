FROM rust:1-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        pkg-config \
        libssl-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY src/rmf2_task_orchestrator_gametl/ .
RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /build/target/release/rmf2_task_orchestrator ./rmf2_task_orchestrator
COPY config/task_orchestrator.toml ./config.toml

EXPOSE 2727
CMD ["./rmf2_task_orchestrator"]
