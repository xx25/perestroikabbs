#!/bin/bash

# Deployment script for Perestroika BBS Docker setup
# Usage: ./deploy.sh [dev|prod]

set -e

ENVIRONMENT=${1:-dev}
COMPOSE_FILE="docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     PERESTROIKA BBS DOCKER DEPLOYMENT        ║${NC}"
echo -e "${BLUE}║     Environment: ${ENVIRONMENT}                     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo

# Check for Docker and Docker Compose
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

# Production environment setup
if [ "$ENVIRONMENT" = "prod" ]; then
    echo -e "${YELLOW}Setting up production environment...${NC}"

    # Check for production compose file
    if [ -f "docker-compose.prod.yml" ]; then
        COMPOSE_FILE="docker-compose.prod.yml"
    fi

    # Ensure production config exists
    if [ ! -f "config.toml" ]; then
        if [ -f "config.docker.toml" ]; then
            cp config.docker.toml config.toml
            echo -e "${YELLOW}Created config.toml from config.docker.toml${NC}"
            echo -e "${RED}Please update config.toml with production settings${NC}"
            exit 1
        fi
    fi
fi

# Pull latest images
echo -e "${YELLOW}Pulling latest images...${NC}"
docker compose -f $COMPOSE_FILE pull

# Build BBS image
echo -e "${YELLOW}Building BBS image...${NC}"
docker compose -f $COMPOSE_FILE build --no-cache

# Stop existing containers
echo -e "${YELLOW}Stopping existing containers...${NC}"
docker compose -f $COMPOSE_FILE down

# Start services
echo -e "${YELLOW}Starting services...${NC}"
docker compose -f $COMPOSE_FILE up -d

# Wait for MySQL to be ready
echo -e "${YELLOW}Waiting for MySQL to be ready...${NC}"
for i in {1..30}; do
    if docker compose -f $COMPOSE_FILE exec mysql mysqladmin ping -h localhost --silent 2>/dev/null; then
        echo -e "${GREEN}MySQL is ready!${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
docker compose -f $COMPOSE_FILE exec bbs python -m alembic upgrade head

# Check service status
echo
echo -e "${GREEN}Service Status:${NC}"
docker compose -f $COMPOSE_FILE ps

# Display connection info
echo
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          DEPLOYMENT COMPLETE                 ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo
echo -e "${BLUE}BBS is running on port 2323${NC}"
echo -e "${BLUE}Connect with: telnet $(hostname -I | awk '{print $1}') 2323${NC}"
echo
echo -e "${YELLOW}View logs: docker compose -f $COMPOSE_FILE logs -f bbs${NC}"
echo -e "${YELLOW}Stop BBS: docker compose -f $COMPOSE_FILE down${NC}"