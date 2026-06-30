# Detail Docker Instructions

## Build Docker locally

To build the docker image locally, simply run

```bash
docker build . --tag ghcr.io/ros-industrial/rmf2-ui/dashboard:local
docker run -p 3000:80 --rm ghcr.io/ros-industrial/rmf2-ui/dashboard:local
```

If you're running this as part of the larger RMF ``rmf2-blue-ocean-stack, bring it up from the umbrella repo root with the real-demo env files and the `ui` service:

```bash
docker compose --env-file config/config.env --env-file config/config-real.env up --build ui
```
