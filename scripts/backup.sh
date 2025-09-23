#!/bin/bash

# Perestroika BBS Backup Script
# Creates timestamped backups of database and file areas

set -e

# Configuration
BACKUP_DIR="/var/backups/bbs"
DB_NAME="perestroika_bbs"
DB_USER="bbs_user"
FILES_DIR="/var/lib/bbs"
KEEP_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Perestroika BBS Backup Utility       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Function to check if command was successful
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
    else
        echo -e "${RED}✗${NC} $1"
        exit 1
    fi
}

# Backup database
echo -e "${YELLOW}Backing up database...${NC}"
DB_BACKUP="$BACKUP_DIR/db_${DB_NAME}_${TIMESTAMP}.sql.gz"

if [ -z "$DB_PASSWORD" ]; then
    echo -n "Enter MySQL password for user $DB_USER: "
    read -s DB_PASSWORD
    echo
fi

mysqldump -u "$DB_USER" -p"$DB_PASSWORD" \
    --single-transaction \
    --routines \
    --triggers \
    --add-drop-database \
    --databases "$DB_NAME" | gzip > "$DB_BACKUP"

check_status "Database backed up to $DB_BACKUP"

# Get database size
DB_SIZE=$(du -h "$DB_BACKUP" | cut -f1)
echo "  Database backup size: $DB_SIZE"

# Backup file areas
echo -e "\n${YELLOW}Backing up file areas...${NC}"
FILES_BACKUP="$BACKUP_DIR/files_${TIMESTAMP}.tar.gz"

if [ -d "$FILES_DIR" ]; then
    tar czf "$FILES_BACKUP" \
        --exclude="*.tmp" \
        --exclude="temp/*" \
        -C "$(dirname "$FILES_DIR")" \
        "$(basename "$FILES_DIR")"

    check_status "Files backed up to $FILES_BACKUP"

    FILES_SIZE=$(du -h "$FILES_BACKUP" | cut -f1)
    echo "  Files backup size: $FILES_SIZE"
else
    echo -e "${YELLOW}Warning: Files directory $FILES_DIR not found${NC}"
fi

# Backup configuration files
echo -e "\n${YELLOW}Backing up configuration...${NC}"
CONFIG_BACKUP="$BACKUP_DIR/config_${TIMESTAMP}.tar.gz"

# Find BBS installation directory
BBS_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"

if [ -f "$BBS_DIR/config.toml" ]; then
    tar czf "$CONFIG_BACKUP" \
        -C "$BBS_DIR" \
        config.toml \
        config.example.toml \
        alembic.ini \
        2>/dev/null || true

    check_status "Configuration backed up to $CONFIG_BACKUP"
fi

# Backup ANSI/RIP assets
echo -e "\n${YELLOW}Backing up assets...${NC}"
ASSETS_BACKUP="$BACKUP_DIR/assets_${TIMESTAMP}.tar.gz"

if [ -d "$BBS_DIR/bbs/app/assets" ]; then
    tar czf "$ASSETS_BACKUP" \
        -C "$BBS_DIR/bbs/app" \
        assets/

    check_status "Assets backed up to $ASSETS_BACKUP"
fi

# Create backup manifest
echo -e "\n${YELLOW}Creating backup manifest...${NC}"
MANIFEST="$BACKUP_DIR/manifest_${TIMESTAMP}.txt"

cat > "$MANIFEST" << EOF
Perestroika BBS Backup Manifest
================================
Timestamp: $TIMESTAMP
Date: $(date)
Host: $(hostname)

Files:
------
Database: $(basename "$DB_BACKUP") ($DB_SIZE)
Files: $(basename "$FILES_BACKUP") (${FILES_SIZE:-N/A})
Config: $(basename "$CONFIG_BACKUP")
Assets: $(basename "$ASSETS_BACKUP")

Database Info:
--------------
Database Name: $DB_NAME
Tables backed up:
$(mysql -u "$DB_USER" -p"$DB_PASSWORD" -e "USE $DB_NAME; SHOW TABLES;" 2>/dev/null | tail -n +2)

Backup Command:
---------------
$0 $@

Notes:
------
To restore from this backup, use:
  ./restore.sh $TIMESTAMP

EOF

check_status "Manifest created at $MANIFEST"

# Clean up old backups
echo -e "\n${YELLOW}Cleaning up old backups...${NC}"
find "$BACKUP_DIR" -type f -name "*.gz" -mtime +$KEEP_DAYS -delete
find "$BACKUP_DIR" -type f -name "*.txt" -mtime +$KEEP_DAYS -delete
check_status "Old backups cleaned (kept last $KEEP_DAYS days)"

# Create latest symlinks
echo -e "\n${YELLOW}Updating latest backup symlinks...${NC}"
ln -sf "$DB_BACKUP" "$BACKUP_DIR/latest_db.sql.gz"
ln -sf "$FILES_BACKUP" "$BACKUP_DIR/latest_files.tar.gz"
ln -sf "$CONFIG_BACKUP" "$BACKUP_DIR/latest_config.tar.gz"
ln -sf "$MANIFEST" "$BACKUP_DIR/latest_manifest.txt"

# Summary
echo
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo -e "${GREEN}Backup completed successfully!${NC}"
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo
echo "Backup location: $BACKUP_DIR"
echo "Backup ID: $TIMESTAMP"
echo
echo "Backed up:"
echo "  ✓ Database ($DB_SIZE)"
[ -n "$FILES_SIZE" ] && echo "  ✓ Files ($FILES_SIZE)"
echo "  ✓ Configuration"
echo "  ✓ Assets"
echo
echo "Total backup size: $(du -sh "$BACKUP_DIR" | cut -f1)"
echo
echo "To restore this backup, run:"
echo "  ${BACKUP_DIR%/*}/scripts/restore.sh $TIMESTAMP"