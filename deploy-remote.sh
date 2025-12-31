#!/bin/bash
# Remote deployment script for Perestroika BBS
# Run from dev machine to deploy to production server

set -e

# Configuration
REMOTE_HOST="192.168.91.2"
REMOTE_USER="${DEPLOY_USER:-dp}"
REMOTE_PATH="/opt/perestroika-bbs"
COMPOSE_FILE="docker-compose.external-db.yml"

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
    echo "  init        - First-time server setup (create dirs, configure MySQL)"
    echo "  deploy      - Full deploy (sync + rebuild + restart)"
    echo "  sync        - Sync files only (no restart)"
    echo "  restart     - Restart containers only"
    echo "  stop        - Stop all containers"
    echo "  logs        - View remote logs"
    echo "  status      - Check remote status"
    echo "  shell       - SSH into remote server"
    echo "  migrate     - Run database migrations"
    echo "  config-db   - Reconfigure MySQL connection settings"
    echo "  create-admin - Create admin user (after first deploy)"
    echo ""
    echo "First-time deployment (uses existing remote MySQL):"
    echo "  1. $0 init        # Configure remote MySQL connection"
    echo "  2. $0 deploy      # Deploy BBS container"
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

    # Configure external MySQL connection
    log "Setting up external MySQL connection..."

    echo ""
    echo -e "${YELLOW}Enter remote MySQL server details:${NC}"
    read -p "MySQL host [localhost]: " DB_HOST
    DB_HOST=${DB_HOST:-localhost}
    read -p "MySQL port [3306]: " DB_PORT
    DB_PORT=${DB_PORT:-3306}
    read -p "MySQL database name [perestroika_bbs]: " DB_NAME
    DB_NAME=${DB_NAME:-perestroika_bbs}
    read -p "MySQL username: " DB_USER
    read -p "MySQL password: " -s DB_PASSWORD
    echo ""
    echo ""

    # Create .env file with database credentials
    log "Creating environment file..."
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "cat > ${REMOTE_PATH}/.env << 'ENVEOF'
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
ENVEOF"
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "chmod 600 ${REMOTE_PATH}/.env"
    success "Environment file created"

    # Test MySQL connection
    log "Testing MySQL connection..."
    if ssh "${REMOTE_USER}@${REMOTE_HOST}" "mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -p'${DB_PASSWORD}' -e 'SELECT 1' ${DB_NAME} > /dev/null 2>&1"; then
        success "MySQL connection successful"
    else
        warn "Could not connect to MySQL. Please verify credentials and ensure database exists."
        echo -e "${YELLOW}You may need to create the database manually:${NC}"
        echo "  CREATE DATABASE ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    fi

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

# Reconfigure database connection
config_db() {
    log "Reconfiguring MySQL connection..."

    echo ""
    echo -e "${YELLOW}Enter remote MySQL server details:${NC}"
    read -p "MySQL host [localhost]: " DB_HOST
    DB_HOST=${DB_HOST:-localhost}
    read -p "MySQL port [3306]: " DB_PORT
    DB_PORT=${DB_PORT:-3306}
    read -p "MySQL database name [perestroika_bbs]: " DB_NAME
    DB_NAME=${DB_NAME:-perestroika_bbs}
    read -p "MySQL username: " DB_USER
    read -p "MySQL password: " -s DB_PASSWORD
    echo ""
    echo ""

    # Update .env file
    log "Updating environment file..."
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "cat > ${REMOTE_PATH}/.env << ENVEOF
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
ENVEOF"
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "chmod 600 ${REMOTE_PATH}/.env"
    success "Environment file updated"

    # Regenerate config and restart
    generate_config

    log "Restarting BBS..."
    remote_exec "docker compose -f ${COMPOSE_FILE} restart"
    success "BBS restarted with new database configuration"
}

# Generate config.toml from .env file
generate_config() {
    log "Generating config.toml from environment..."

    # Read database credentials from .env and generate config
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "cd ${REMOTE_PATH} && source .env && cat > config.toml << CONFIGEOF
[server]
host = \"0.0.0.0\"
port = 2323
motd_asset = \"ansi/motd.ans\"
max_connections = 100
connection_timeout = 300
welcome_message = \"Welcome to Perestroika BBS!\"

[telnet]
enable_naws = true
enable_binary = true
enable_echo = false
default_cols = 80
default_rows = 24

[db]
dsn = \"mysql+aiomysql://\${DB_USER}:\${DB_PASSWORD}@\${DB_HOST}:\${DB_PORT}/\${DB_NAME}\"
echo = false
pool_size = 20
max_overflow = 10
pool_timeout = 30
pool_recycle = 3600

[transfers]
rz_path = \"/usr/bin/rz\"
sz_path = \"/usr/bin/sz\"
ckermit_path = \"/usr/bin/kermit\"
download_root = \"/var/lib/bbs/files\"
upload_root = \"/var/lib/bbs/uploads\"
max_upload_size = 10485760

[security]
argon2_time_cost = 3
argon2_memory_cost = 65536
argon2_parallelism = 4
max_login_attempts = 5
login_throttle_seconds = 60
session_timeout = 3600
require_secure_passwords = true
min_password_length = 8

[charset]
default_encoding = \"utf-8\"
supported_encodings = [\"utf-8\", \"ascii\", \"cp866\", \"koi8-r\", \"koi8-u\", \"windows-1251\", \"iso-8859-5\", \"x-mac-cyrillic\"]

[logging]
level = \"INFO\"
file_path = \"/var/log/bbs/perestroika.log\"
max_bytes = 10485760
backup_count = 5
CONFIGEOF"
    success "Config generated"
}

# Full deployment
deploy() {
    echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     PERESTROIKA BBS REMOTE DEPLOYMENT        ║${NC}"
    echo -e "${BLUE}║     Target: ${REMOTE_HOST}                       ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
    echo

    # Check if .env exists
    if ! ssh "${REMOTE_USER}@${REMOTE_HOST}" "test -f ${REMOTE_PATH}/.env"; then
        error "No .env file found. Run '$0 init' first."
    fi

    sync_files

    # Generate config.toml from .env
    generate_config

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
    config-db)
        config_db
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
