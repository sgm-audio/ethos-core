# Deploy with Docker

## Build the Image

```bash
docker build -t ethos-core .
```

The Dockerfile uses a multi-stage build with `uv` for dependency management, runs as a non-root user, and includes a `urllib` healthcheck.

## Run with Docker Compose

### Development

```bash
docker-compose up
```

This starts the API server on port 8000 with volume mounts for live development.

### Production

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Environment Variables

Create a `.env` file from the template:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `ETHOS_HOST` | `0.0.0.0` | API server bind address |
| `ETHOS_PORT` | `8000` | API server port |
| `ETHOS_LOG_LEVEL` | `INFO` | Logging level |
| `ETHOS_MAX_WORKERS` | `4` | Max concurrent processing workers |
| `RAY_ADDRESS` | `auto` | Ray cluster address |

## Kubernetes Deployment

Manifests are provided in the `deployment/` directory:

```bash
kubectl apply -f deployment/
```

This creates:

- **Deployment** with resource limits and liveness/readiness probes
- **Service** (ClusterIP) on port 8000
- **ConfigMap** with environment configuration
- **HorizontalPodAutoscaler** (2–10 replicas, CPU target 70%)

## Health Monitoring

```bash
# Health check
curl http://localhost:8000/health

# Prometheus metrics
curl http://localhost:8000/metrics
```

Metrics include `ethos_active_agents`, `ethos_jobs_total`, and `ethos_pipeline_stages`.
