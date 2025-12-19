#!/bin/bash
# Deployment script for Perestroika BBS on 192.168.91.2

set -e

echo "======================================"
echo "Perestroika BBS Deployment Script"
echo "Target: 192.168.91.2"
echo "======================================"

# Check if running as root (recommended for /opt access)
if [ "$EUID" -ne 0 ]; then
   echo "Warning: Not running as root. You may need sudo for /opt/bbs directory creation."
fi

# 1. Create directories
echo ""
echo "1. Creating directories in /opt/bbs..."
sudo mkdir -p /opt/bbs/{files,uploads,logs}
sudo chmod 755 /opt/bbs
sudo chmod 777 /opt/bbs/{files,uploads,logs}

# 2. MySQL Setup
echo ""
echo "2. MySQL Database Setup..."
echo "Please ensure MySQL is accessible from Docker containers."
echo ""
read -p "Enter MySQL root password (for database creation): " -s MYSQL_ROOT_PASS
echo ""

# Create database and user
mysql -u root -p"$MYSQL_ROOT_PASS" <<EOF
CREATE DATABASE IF NOT EXISTS perestroika_bbs CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'bbs'@'%' IDENTIFIED BY 'CHANGE_THIS_PASSWORD';
GRANT ALL PRIVILEGES ON perestroika_bbs.* TO 'bbs'@'%';
FLUSH PRIVILEGES;
EOF

echo "Database created successfully!"
echo ""
echo "IMPORTANT: Edit config.production.toml and change the database password!"
echo ""

# 3. Configure production settings
echo "3. Configuration..."
echo "Please edit config.production.toml and set:"
echo "  - Database password for 'bbs' user"
echo "  - Any other custom settings"
echo ""
read -p "Press Enter when config.production.toml is ready..."

# 4. Build and start Docker container
echo ""
echo "4. Building Docker image..."
docker compose -f docker-compose.production.yml build

echo ""
echo "5. Starting BBS service..."
docker compose -f docker-compose.production.yml up -d

# 6. Check status
echo ""
echo "6. Checking service status..."
sleep 3
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs --tail=20

echo ""
echo "======================================"
echo "Deployment Complete!"
echo "======================================"
echo ""
echo "BBS should now be accessible at:"
echo "  telnet 192.168.91.2 2323"
echo ""
echo "Directories:"
echo "  Files: /opt/bbs/files"
echo "  Uploads: /opt/bbs/uploads"
echo "  Logs: /opt/bbs/logs"
echo ""
echo "To manage the service:"
echo "  Start:   docker compose -f docker-compose.production.yml up -d"
echo "  Stop:    docker compose -f docker-compose.production.yml down"
echo "  Logs:    docker compose -f docker-compose.production.yml logs -f"
echo "  Restart: docker compose -f docker-compose.production.yml restart"
echo ""