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
    echo "  init      - First-time server setup (create dirs, secrets, check Docker)"
    echo "  deploy    - Full deploy (sync + rebuild + restart)"
    echo "  sync      - Sync files only (no restart)"
    echo "  restart   - Restart containers only"
    echo "  stop      - Stop all containers"
    echo "  logs      - View remote logs"
    echo "  status    - Check remote status"
    echo "  shell     - SSH into remote server"
    echo "  migrate   - Run database migrations"
    echo "  create-admin - Create admin user (after first deploy)"
    echo ""
    echo "First-time deployment:"
    echo "  1. $0 init"
    echo "  2. $0 deploy"
    echo "  3. $0 create-admin"
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

# First-time server initialization
init_server() {
    echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     PERESTROIKA BBS SERVER INITIALIZATION    ║${NC}"
    echo -e "${BLUE}║     Target: ${REMOTE_HOST}                       ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
    echo

    # Check SSH connection
    log "Checking SSH connection..."
    if ! ssh -o ConnectTimeout=5 "${REMOTE_USER}@${REMOTE_HOST}" "echo 'connected'" > /dev/null 2>&1; then
        error "Cannot connect to ${REMOTE_USER}@${REMOTE_HOST}"
    fi
    success "SSH connection OK"

    # Check Docker
    log "Checking Docker installation..."
    if ! ssh "${REMOTE_USER}@${REMOTE_HOST}" "docker --version" > /dev/null 2>&1; then
        error "Docker is not installed on ${REMOTE_HOST}. Please install Docker first."
    fi
    success "Docker is installed"

    if ! ssh "${REMOTE_USER}@${REMOTE_HOST}" "docker compose version" > /dev/null 2>&1; then
        error "Docker Compose is not installed on ${REMOTE_HOST}. Please install Docker Compose first."
    fi
    success "Docker Compose is installed"

    # Create directory
    log "Creating ${REMOTE_PATH}..."
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "sudo mkdir -p ${REMOTE_PATH} && sudo chown ${REMOTE_USER}:${REMOTE_USER} ${REMOTE_PATH}"
    success "Directory created"

    # Create secrets
    log "Setting up secrets..."

    echo ""
    echo -e "${YELLOW}Enter MySQL passwords for production:${NC}"
    read -p "MySQL ROOT password: " -s MYSQL_ROOT_PASS
    echo ""
    read -p "MySQL BBS user password: " -s MYSQL_BBS_PASS
    echo ""
    echo ""

    ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p ${REMOTE_PATH}/secrets && chmod 700 ${REMOTE_PATH}/secrets"
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "echo '${MYSQL_ROOT_PASS}' > ${REMOTE_PATH}/secrets/mysql_root_password.txt"
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "echo '${MYSQL_BBS_PASS}' > ${REMOTE_PATH}/secrets/mysql_password.txt"
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "chmod 600 ${REMOTE_PATH}/secrets/*.txt"
    success "Secrets created"

    echo
    echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║       SERVER INITIALIZATION COMPLETE         ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
    echo
    echo -e "Next steps:"
    echo -e "  ${BLUE}1.${NC} ./deploy-remote.sh deploy"
    echo -e "  ${BLUE}2.${NC} ./deploy-remote.sh create-admin"
    echo
}

# Create admin user
create_admin() {
    log "Creating admin user..."
    echo ""
    read -p "Admin username: " ADMIN_USER
    read -p "Admin password: " -s ADMIN_PASS
    echo ""
    read -p "Admin email: " ADMIN_EMAIL

    remote_exec "docker compose -f ${COMPOSE_FILE} exec -T bbs python -c \"
from bbs.storage.repository import UserRepository
from bbs.storage.database import async_session
from bbs.core.security import hash_password
import asyncio

async def create():
    async with async_session() as session:
        repo = UserRepository(session)
        user = await repo.create_user(
            username='${ADMIN_USER}',
            password_hash=hash_password('${ADMIN_PASS}'),
            email='${ADMIN_EMAIL}',
            access_level=255
        )
        await session.commit()
        print(f'Admin user {user.username} created with access level 255')

asyncio.run(create())
\""
    success "Admin user created"
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
case "${1:-help}" in
    init)
        init_server
        ;;
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
    stop)
        log "Stopping containers..."
        remote_exec "docker compose -f ${COMPOSE_FILE} down"
        success "Containers stopped"
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
    create-admin)
        create_admin
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        error "Unknown command: $1"
        ;;
esac
