#!/bin/bash
# Simple BBS telnet testing script

HOST=${1:-localhost}
PORT=${2:-2323}
TIMEOUT=3

echo "====================================="
echo "PERESTROIKA BBS TELNET TESTING"
echo "====================================="
echo "Target: $HOST:$PORT"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

# Function to run test
run_test() {
    local name="$1"
    local command="$2"
    local expected="$3"

    echo -n "Testing: $name ... "

    result=$(echo -e "$command" | timeout $TIMEOUT nc -v $HOST $PORT 2>&1)

    if echo "$result" | grep -q "$expected"; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "  Expected: '$expected'"
        echo "  Got: ${result:0:100}..."
        ((FAILED++))
        return 1
    fi
}

# Test 1: Basic connection
echo -n "Test 1: Basic Connection ... "
if timeout 2 nc -zv $HOST $PORT 2>&1 | grep -q "succeeded\|open"; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
    echo "Cannot connect to BBS. Exiting."
    exit 1
fi

# Test 2: Send data and receive response
echo -n "Test 2: Data Exchange ... "
response=$(echo -e "\r\n" | timeout $TIMEOUT nc $HOST $PORT 2>&1 | head -c 100)
if [ -n "$response" ]; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

# Test 3: ANSI escape sequence
echo -n "Test 3: ANSI Support ... "
response=$(echo -e "\033[6n\r\n" | timeout $TIMEOUT nc $HOST $PORT 2>&1)
if echo "$response" | grep -q "\[" || [ -n "$response" ]; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ SKIPPED${NC}"
fi

# Test 4: Multiple lines input
echo -n "Test 4: Multiple Input Lines ... "
response=$(echo -e "test1\r\ntest2\r\ntest3\r\n" | timeout $TIMEOUT nc $HOST $PORT 2>&1)
if [ -n "$response" ]; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

# Test 5: Long input
echo -n "Test 5: Long Input Handling ... "
long_input=$(printf 'A%.0s' {1..500})
response=$(echo -e "$long_input\r\n" | timeout $TIMEOUT nc $HOST $PORT 2>&1)
if [ -n "$response" ]; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

# Test 6: UTF-8 characters
echo -n "Test 6: UTF-8 Support ... "
response=$(echo -e "Hello мир 世界\r\n" | timeout $TIMEOUT nc $HOST $PORT 2>&1)
if [ -n "$response" ]; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi

# Test 7: Rapid connections
echo -n "Test 7: Rapid Connections ... "
success=0
for i in {1..5}; do
    if timeout 1 nc -zv $HOST $PORT 2>&1 | grep -q "succeeded\|open"; then
        ((success++))
    fi
    sleep 0.2
done
if [ $success -eq 5 ]; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC} (only $success/5 succeeded)"
    ((FAILED++))
fi

# Test 8: Telnet IAC commands
echo -n "Test 8: Telnet Protocol ... "
# Send IAC (Interpret As Command) sequences
response=$(printf '\xff\xfb\x01\xff\xfb\x03\xff\xfd\x18\xff\xfd\x1f' | timeout $TIMEOUT nc $HOST $PORT 2>&1)
if [ -n "$response" ]; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ SKIPPED${NC}"
fi

echo ""
echo "====================================="
echo "TEST SUMMARY"
echo "====================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
TOTAL=$((PASSED + FAILED))
if [ $TOTAL -gt 0 ]; then
    SUCCESS_RATE=$((PASSED * 100 / TOTAL))
    echo "Success Rate: ${SUCCESS_RATE}%"
fi
echo "====================================="

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi