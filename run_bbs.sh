#!/bin/bash

# Perestroika BBS Startup Script

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         PERESTROIKA BBS SYSTEM               ║${NC}"
echo -e "${GREEN}║         Starting up...                       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
REQUIRED_VERSION="3.11"

if [ $(echo "$PYTHON_VERSION < $REQUIRED_VERSION" | bc -l) -eq 1 ]; then
    echo -e "${RED}Error: Python $REQUIRED_VERSION or higher is required (found $PYTHON_VERSION)${NC}"
    exit 1
fi

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/upgrade dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Check MySQL connection
echo -e "${YELLOW}Checking MySQL connection...${NC}"
python3 -c "
import sys
import asyncio
from bbs.app.storage.db import init_database
try:
    asyncio.run(init_database())
    print('✓ MySQL connection successful')
except Exception as e:
    print(f'✗ MySQL connection failed: {e}')
    sys.exit(1)
" || exit 1

# Check for config file
if [ ! -f "config.toml" ]; then
    if [ -f "config.example.toml" ]; then
        echo -e "${YELLOW}No config.toml found. Copying example config...${NC}"
        cp config.example.toml config.toml
        echo -e "${YELLOW}Please edit config.toml with your settings${NC}"
        exit 1
    else
        echo -e "${RED}Error: No configuration file found${NC}"
        exit 1
    fi
fi

# Check for external dependencies
echo -e "${YELLOW}Checking external dependencies...${NC}"

if command -v sz &> /dev/null; then
    echo "✓ ZMODEM (lrzsz) found"
else
    echo "✗ ZMODEM (lrzsz) not found - install with: sudo apt-get install lrzsz"
fi

if command -v kermit &> /dev/null; then
    echo "✓ Kermit found"
else
    echo "✗ Kermit not found - install with: sudo apt-get install ckermit"
fi

echo

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
python3 -m alembic upgrade head

# Start the BBS
echo
echo -e "${GREEN}Starting BBS on port 2323...${NC}"
echo -e "${GREEN}Connect with: telnet localhost 2323${NC}"
echo
echo -e "${YELLOW}Press Ctrl-C to stop the server${NC}"
echo

# Run the BBS
python3 -m bbs.app.main "$@"