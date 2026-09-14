# ETHOS Core - Docker Configuration Guide

## Project Structure
```
.
├── Dockerfile              # Multi-stage build for production
├── docker-compose.yml      # Development environment with hot-reload
├── docker-compose.prod.yml # Production-minimal setup
├── .dockerignore           # Optimize build context
└── docker-build.sh         # Quick build script
```

## Building the Image

### Quick Build
```bash
./docker-build.sh
```

### Standard Build
```bash
docker build -t ethos-core:latest .
```

## Running Containers

### Development (with hot-reload)
```bash
docker compose up -d
```
- FastAPI runs on port 8000
- Source code synced via volume mounts
- Redis on 6379 for caching
- PostgreSQL on 5432 for persistence
- Logs: `docker compose logs -f ethos-core`

### Production
```bash
docker compose -f docker-compose.prod.yml up -d
```
- Minimal footprint, no dev dependencies
- Resource limits enforced (2 CPU, 4GB RAM)
- Auto-restart on failure
- Logs: `docker logs -f <container-id>`

## Common Commands

**View running containers:**
```bash
docker compose ps
```

**Execute command in container:**
```bash
docker compose exec ethos-core pytest tests/
```

**View logs:**
```bash
docker compose logs -f ethos-core --tail=100
```

**Stop all services:**
```bash
docker compose down
```

**Remove all containers and volumes:**
```bash
docker compose down -v
```

## Key Features

- **Multi-stage build**: Minimal final image size, fast builds with caching
- **Non-root user**: Security hardening (appuser:1000)
- **Health checks**: Automated container health monitoring
- **Volume mounts**: Hot-reload for development
- **Network isolation**: Dedicated ethos-network for service communication
- **Environment management**: Separate configs for dev/prod

## Dockerfile Optimizations

1. **Layer ordering**: Dependencies cached before source code
2. **Virtual environment**: Isolated Python packages in .venv
3. **System dependencies**: Audio libraries (libsndfile1, ffmpeg) included
4. **Multi-stage**: Builder stage removed from final image (~500MB saved)
5. **User isolation**: Non-root execution for security

## Environment Variables

**Development** (docker-compose.yml):
- `LOG_LEVEL=DEBUG`
- `PYTHONUNBUFFERED=1`

**Production** (docker-compose.prod.yml):
- `LOG_LEVEL=INFO`
- Resource limits: 2 CPU / 4GB RAM

## Troubleshooting

**Build fails with "permission denied":**
- Windows: Use WSL2 backend for Docker Desktop
- Linux: Add user to docker group: `sudo usermod -aG docker $USER`

**Out of memory during build:**
- Increase Docker Desktop memory allocation
- Allocate at least 4GB for PyTorch builds

**Port already in use:**
- Change port mapping in compose: `"9000:8000"`

**Volume mount issues (Windows):**
- Use forward slashes: `./src:/app/src`
- Ensure path is within WSL2 working directory
