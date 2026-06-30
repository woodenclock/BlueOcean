FROM node:24 AS build

WORKDIR /app
COPY . /app

RUN corepack enable && \
    corepack prepare pnpm@latest-11 --activate

RUN pnpm install

ARG SCHEDULER_PORT=8089
ARG VDA5050_PORT=8000
ARG TASK_ORCHESTRATOR_PORT=2727
RUN printf '%s\n' \
    'BASE_URL=http://localhost' \
    'VITE_NETWORK_MOCK_CONNECTED=true' \
    "VITE_RTS_BASE=http://localhost:${SCHEDULER_PORT}" \
    "VITE_RTO_BASE=http://localhost:${TASK_ORCHESTRATOR_PORT}" \
    "VITE_LAUNCHER_BASE=http://localhost:8083" \
    "VITE_BROKER_STATUS_BASE=http://localhost:${VDA5050_PORT}" \
    'VITE_BROKER_NGSI_LD_BASE=http://localhost:9999/ngsi-ld' \
    > apps/dashboard/.env.production

RUN pnpm run -r build --mode production

FROM nginx:alpine AS dashboard

# Internal nginx listen port. Read from a variable (overridable via build arg /
# config), defaults to 80. The host-side port is mapped separately via UI_PORT
# in docker-compose.
ARG NGINX_PORT=80
ENV NGINX_PORT=${NGINX_PORT}
# Only substitute ${NGINX_PORT} in the template so nginx variables like $uri
# are left untouched by envsubst at container start.
ENV NGINX_ENVSUBST_FILTER=NGINX_PORT

COPY --from=build /app/apps/dashboard/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template

EXPOSE ${NGINX_PORT}
