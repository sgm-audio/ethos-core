#!/bin/bash
# Docker setup for ETHOS Core

set -e

echo "Building ETHOS Core Docker image..."
docker build -t ethos-core:latest .

echo "Build complete!"
echo ""
echo "To start development environment:"
echo "  docker compose up -d"
echo ""
echo "To start production environment:"
echo "  docker compose -f docker-compose.prod.yml up -d"
echo ""
echo "To view logs:"
echo "  docker compose logs -f ethos-core"
echo ""
echo "To run tests inside container:"
echo "  docker compose exec ethos-core pytest"
echo ""
echo "To stop containers:"
echo "  docker compose down"
