#!/bin/bash

# Perestroika BBS Restore Script
# Restores from timestamped backups

set -e

# Configuration
BACKUP_DIR="/var/backups/bbs"
DB_NAME="perestroika_bbs"
DB_USER="bbs_user"
FILES_DIR="/var/lib/bbs"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Perestroika BBS Restore Utility      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo

# Check for timestamp argument
if [ $# -eq 0 ]; then
    echo "Usage: $0 <timestamp>"
    echo
    echo "Available backups:"

    if [ -d "$BACKUP_DIR" ]; then
        for manifest in $(ls -t "$BACKUP_DIR"/manifest_*.txt 2>/dev/null | head -10); do
            timestamp=$(basename "$manifest" | sed 's/manifest_\(.*\)\.txt/\1/')
            date=$(grep "^Date:" "$manifest" | cut -d' ' -f2-)
            echo "  $timestamp - $date"
        done

        if [ -f "$BACKUP_DIR/latest_manifest.txt" ]; then
            echo
            echo "To restore the latest backup:"
            echo "  $0 latest"
        fi
    else
        echo "  No backups found in $BACKUP_DIR"
    fi

    exit 1
fi

TIMESTAMP="$1"

# Handle "latest" keyword
if [ "$TIMESTAMP" == "latest" ]; then
    if [ -f "$BACKUP_DIR/latest_manifest.txt" ]; then
        TIMESTAMP=$(basename "$(readlink "$BACKUP_DIR/latest_manifest.txt")" | sed 's/manifest_\(.*\)\.txt/\1/')
        echo -e "${YELLOW}Using latest backup: $TIMESTAMP${NC}"
    else
        echo -e "${RED}No latest backup found${NC}"
        exit 1
    fi
fi

# Function to check if command was successful
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
    else
        echo -e "${RED}✗${NC} $1"
        exit 1
    fi
}

# Check if backup files exist
MANIFEST="$BACKUP_DIR/manifest_${TIMESTAMP}.txt"
if [ ! -f "$MANIFEST" ]; then
    echo -e "${RED}Error: Backup with timestamp $TIMESTAMP not found${NC}"
    exit 1
fi

echo "Found backup from: $(grep "^Date:" "$MANIFEST" | cut -d' ' -f2-)"
echo

# Confirm restoration
echo -e "${YELLOW}WARNING: This will replace existing data!${NC}"
echo "The following will be restored:"

DB_BACKUP="$BACKUP_DIR/db_${DB_NAME}_${TIMESTAMP}.sql.gz"
[ -f "$DB_BACKUP" ] && echo "  • Database from $(basename "$DB_BACKUP")"

FILES_BACKUP="$BACKUP_DIR/files_${TIMESTAMP}.tar.gz"
[ -f "$FILES_BACKUP" ] && echo "  • Files from $(basename "$FILES_BACKUP")"

CONFIG_BACKUP="$BACKUP_DIR/config_${TIMESTAMP}.tar.gz"
[ -f "$CONFIG_BACKUP" ] && echo "  • Configuration from $(basename "$CONFIG_BACKUP")"

ASSETS_BACKUP="$BACKUP_DIR/assets_${TIMESTAMP}.tar.gz"
[ -f "$ASSETS_BACKUP" ] && echo "  • Assets from $(basename "$ASSETS_BACKUP")"

echo
read -p "Do you want to continue? (yes/NO): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo

# Stop BBS service if running
if systemctl is-active --quiet perestroika-bbs 2>/dev/null; then
    echo -e "${YELLOW}Stopping BBS service...${NC}"
    sudo systemctl stop perestroika-bbs
    check_status "BBS service stopped"
    RESTART_SERVICE=1
fi

# Get MySQL password
if [ -z "$DB_PASSWORD" ]; then
    echo -n "Enter MySQL password for user $DB_USER: "
    read -s DB_PASSWORD
    echo
fi

# Create safety backup before restore
echo -e "\n${YELLOW}Creating safety backup...${NC}"
SAFETY_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SAFETY_BACKUP="$BACKUP_DIR/pre_restore_${SAFETY_TIMESTAMP}.sql.gz"

mysqldump -u "$DB_USER" -p"$DB_PASSWORD" \
    --single-transaction \
    --routines \
    --triggers \
    --add-drop-database \
    --databases "$DB_NAME" 2>/dev/null | gzip > "$SAFETY_BACKUP"

check_status "Safety backup created at $SAFETY_BACKUP"

# Restore database
if [ -f "$DB_BACKUP" ]; then
    echo -e "\n${YELLOW}Restoring database...${NC}"

    # Drop and recreate database
    mysql -u "$DB_USER" -p"$DB_PASSWORD" << EOF
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME;
EOF

    # Restore from backup
    zcat "$DB_BACKUP" | mysql -u "$DB_USER" -p"$DB_PASSWORD"

    check_status "Database restored from $DB_BACKUP"
else
    echo -e "${YELLOW}Warning: Database backup not found, skipping${NC}"
fi

# Restore files
if [ -f "$FILES_BACKUP" ]; then
    echo -e "\n${YELLOW}Restoring file areas...${NC}"

    # Backup existing files
    if [ -d "$FILES_DIR" ]; then
        mv "$FILES_DIR" "${FILES_DIR}.bak.${SAFETY_TIMESTAMP}"
        echo "  Existing files moved to ${FILES_DIR}.bak.${SAFETY_TIMESTAMP}"
    fi

    # Extract files
    mkdir -p "$FILES_DIR"
    tar xzf "$FILES_BACKUP" -C "$(dirname "$FILES_DIR")"

    check_status "Files restored from $FILES_BACKUP"
else
    echo -e "${YELLOW}Warning: Files backup not found, skipping${NC}"
fi

# Restore configuration (optional)
if [ -f "$CONFIG_BACKUP" ]; then
    echo -e "\n${YELLOW}Configuration backup found.${NC}"
    read -p "Restore configuration files? (y/N): " restore_config

    if [ "$restore_config" == "y" ] || [ "$restore_config" == "Y" ]; then
        BBS_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"

        # Backup existing config
        [ -f "$BBS_DIR/config.toml" ] && cp "$BBS_DIR/config.toml" "$BBS_DIR/config.toml.bak.${SAFETY_TIMESTAMP}"

        tar xzf "$CONFIG_BACKUP" -C "$BBS_DIR"

        check_status "Configuration restored"
        echo -e "${YELLOW}Note: Please review config.toml for any necessary adjustments${NC}"
    fi
fi

# Restore assets (optional)
if [ -f "$ASSETS_BACKUP" ]; then
    echo -e "\n${YELLOW}Assets backup found.${NC}"
    read -p "Restore ANSI/RIP assets? (y/N): " restore_assets

    if [ "$restore_assets" == "y" ] || [ "$restore_assets" == "Y" ]; then
        BBS_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"

        # Backup existing assets
        [ -d "$BBS_DIR/bbs/app/assets" ] && mv "$BBS_DIR/bbs/app/assets" "$BBS_DIR/bbs/app/assets.bak.${SAFETY_TIMESTAMP}"

        tar xzf "$ASSETS_BACKUP" -C "$BBS_DIR/bbs/app"

        check_status "Assets restored"
    fi
fi

# Run database migrations
echo -e "\n${YELLOW}Running database migrations...${NC}"
BBS_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"
cd "$BBS_DIR"

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python3 -m alembic upgrade head 2>/dev/null || echo -e "${YELLOW}Warning: Could not run migrations${NC}"

# Set correct permissions
echo -e "\n${YELLOW}Setting permissions...${NC}"
[ -d "$FILES_DIR" ] && chmod -R 755 "$FILES_DIR"
check_status "Permissions set"

# Restart BBS service if it was running
if [ "$RESTART_SERVICE" == "1" ]; then
    echo -e "\n${YELLOW}Starting BBS service...${NC}"
    sudo systemctl start perestroika-bbs
    check_status "BBS service started"
fi

# Summary
echo
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo -e "${GREEN}Restore completed successfully!${NC}"
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo
echo "Restored from backup: $TIMESTAMP"
echo "Safety backup saved as: $SAFETY_BACKUP"
echo
echo "Next steps:"
echo "  1. Verify the BBS is working correctly"
echo "  2. Review configuration if restored"
echo "  3. Check file permissions if needed"
echo
echo "If restore caused issues, you can restore the safety backup:"
echo "  zcat $SAFETY_BACKUP | mysql -u $DB_USER -p $DB_NAME"