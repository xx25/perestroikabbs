#!/bin/bash
# Remote deployment script for Perestroika BBS
# Run from dev machine to deploy to production server

set -e

# Configuration
REMOTE_HOST="192.168.91.2"
REMOTE_USER="${DEPLOY_USER:-dp}"
REMOTE_PATH="/opt/perestroika-bbs"
COMPOSE_FILE="docker-compose.prod.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  sync      - Sync files only (no restart)"
    echo "  deploy    - Full deploy (sync + rebuild + restart)"
    echo "  restart   - Restart containers only"
    echo "  logs      - View remote logs"
    echo "  status    - Check remote status"
    echo "  shell     - SSH into remote server"
    echo "  migrate   - Run database migrations"
    echo ""
    echo "Environment variables:"
    echo "  DEPLOY_USER  - SSH user (default: dp)"
    exit 1
}

log() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

warn() {
    echo -e "${YELLOW}!${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

# Sync files to remote
sync_files() {
    log "Syncing files to ${REMOTE_HOST}:${REMOTE_PATH}..."

    rsync -avz --delete \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --exclude='.mypy_cache' \
        --exclude='.ruff_cache' \
        --exclude='*.egg-info' \
        --exclude='.env' \
        --exclude='secrets/' \
        --exclude='test-results/' \
        --exclude='*.log' \
        --exclude='.venv' \
        --exclude='venv' \
        ./ "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/"

    success "Files synced"
}

# Run command on remote
remote_exec() {
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "cd ${REMOTE_PATH} && $1"
}

# Full deployment
deploy() {
    echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     PERESTROIKA BBS REMOTE DEPLOYMENT        ║${NC}"
    echo -e "${BLUE}║     Target: ${REMOTE_HOST}                       ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
    echo

    sync_files

    log "Building Docker image..."
    remote_exec "docker compose -f ${COMPOSE_FILE} build"
    success "Image built"

    log "Restarting services..."
    remote_exec "docker compose -f ${COMPOSE_FILE} up -d"
    success "Services restarted"

    log "Waiting for services to start..."
    sleep 3

    log "Running migrations..."
    remote_exec "docker compose -f ${COMPOSE_FILE} exec -T bbs python -m alembic upgrade head" || warn "Migration skipped or failed"

    echo
    echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          DEPLOYMENT COMPLETE                 ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
    echo
    echo -e "Connect: ${BLUE}telnet ${REMOTE_HOST} 2323${NC}"
}

# Main
case "${1:-deploy}" in
    sync)
        sync_files
        ;;
    deploy)
        deploy
        ;;
    restart)
        log "Restarting containers..."
        remote_exec "docker compose -f ${COMPOSE_FILE} restart"
        success "Containers restarted"
        ;;
    logs)
        remote_exec "docker compose -f ${COMPOSE_FILE} logs -f bbs"
        ;;
    status)
        remote_exec "docker compose -f ${COMPOSE_FILE} ps"
        ;;
    shell)
        ssh "${REMOTE_USER}@${REMOTE_HOST}"
        ;;
    migrate)
        log "Running migrations..."
        remote_exec "docker compose -f ${COMPOSE_FILE} exec -T bbs python -m alembic upgrade head"
        success "Migrations complete"
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        error "Unknown command: $1"
        ;;
esac
