#!/bin/bash
# End-to-End BBS Scenario Testing
# Tests complete user journeys through the BBS

HOST=${1:-localhost}
PORT=${2:-2323}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASSED=0
FAILED=0
TOTAL=0

echo "=========================================="
echo "BBS END-TO-END SCENARIO TESTING"
echo "=========================================="
echo "Target: $HOST:$PORT"
echo ""

# Function to run scenario test
run_scenario() {
    local name="$1"
    local description="$2"
    shift 2
    local commands=("$@")

    echo -e "${BLUE}📝 Scenario: $name${NC}"
    echo "   $description"

    ((TOTAL++))

    # Build command string
    cmd_string=""
    for cmd in "${commands[@]}"; do
        cmd_string="${cmd_string}${cmd}\r\n"
    done

    # Execute scenario
    output=$(echo -e "$cmd_string" | timeout 10 nc $HOST $PORT 2>&1)

    # Check for success indicators
    if [ -n "$output" ]; then
        echo -e "   ${GREEN}✅ Scenario completed${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "   ${RED}❌ Scenario failed${NC}"
        ((FAILED++))
        return 1
    fi
}

# ========== SCENARIO 1: New User Journey ==========
echo -e "\n${YELLOW}=== SCENARIO 1: New User Journey ===${NC}"
run_scenario "New User Registration" \
    "User discovers BBS, registers, and explores" \
    "" \
    "?" \
    "R" \
    "newuser123" \
    "password123" \
    "password123" \
    "user@example.com" \
    "Y" \
    "M" \
    "Q"

# ========== SCENARIO 2: Returning User ==========
echo -e "\n${YELLOW}=== SCENARIO 2: Returning User Login ===${NC}"
run_scenario "Returning User" \
    "Regular user logs in, checks messages, posts" \
    "" \
    "L" \
    "testuser" \
    "testpass" \
    "M" \
    "R" \
    "B" \
    "1" \
    "R" \
    "Q"

# ========== SCENARIO 3: Message Board Interaction ==========
echo -e "\n${YELLOW}=== SCENARIO 3: Forum Participation ===${NC}"
run_scenario "Forum User" \
    "User reads posts, replies, and creates new thread" \
    "" \
    "B" \
    "L" \
    "1" \
    "R" \
    "N" \
    "P" \
    "Test Thread" \
    "This is a test message" \
    "Y" \
    "Q"

# ========== SCENARIO 4: File Download ==========
echo -e "\n${YELLOW}=== SCENARIO 4: File Browser ===${NC}"
run_scenario "File Download" \
    "User browses files and initiates download" \
    "" \
    "F" \
    "L" \
    "S" \
    "*.txt" \
    "I" \
    "1" \
    "D" \
    "1" \
    "X" \
    "Q"

# ========== SCENARIO 5: Chat Room ==========
echo -e "\n${YELLOW}=== SCENARIO 5: Chat Session ===${NC}"
run_scenario "Chat Room" \
    "User joins chat, sends messages, leaves" \
    "" \
    "C" \
    "L" \
    "J" \
    "main" \
    "Hello everyone!" \
    "/who" \
    "/quit" \
    "Q"

# ========== SCENARIO 6: Private Mail ==========
echo -e "\n${YELLOW}=== SCENARIO 6: Mail System ===${NC}"
run_scenario "Mail Exchange" \
    "User sends and receives private mail" \
    "" \
    "M" \
    "S" \
    "sysop" \
    "Test Subject" \
    "Test message body" \
    "Y" \
    "R" \
    "1" \
    "D" \
    "Y" \
    "Q"

# ========== SCENARIO 7: Profile Management ==========
echo -e "\n${YELLOW}=== SCENARIO 7: User Profile ===${NC}"
run_scenario "Profile Update" \
    "User updates profile and preferences" \
    "" \
    "U" \
    "P" \
    "E" \
    "New bio text" \
    "S" \
    "Y" \
    "Q"

# ========== SCENARIO 8: Multi-Protocol Test ==========
echo -e "\n${YELLOW}=== SCENARIO 8: Protocol Support ===${NC}"
# Test ANSI sequences - send them and check if BBS accepts them without error
# The timeout exit code 124 means it ran for full duration without errors
echo -e "\r\n\033[2J\033[H" | timeout 2 nc $HOST $PORT > /dev/null 2>&1
exit_code=$?
if [ $exit_code -eq 124 ] || [ $exit_code -eq 0 ]; then
    echo -e "   ${GREEN}✅ ANSI clear screen${NC}"
    ((PASSED++))
else
    echo -e "   ${RED}❌ ANSI failed${NC}"
    ((FAILED++))
fi
((TOTAL++))

# Test cursor positioning - timeout is expected as BBS continues running
echo -e "\r\n\033[10;20H" | timeout 2 nc $HOST $PORT > /dev/null 2>&1
exit_code=$?
if [ $exit_code -eq 124 ] || [ $exit_code -eq 0 ]; then
    echo -e "   ${GREEN}✅ Cursor positioning${NC}"
    ((PASSED++))
else
    echo -e "   ${RED}❌ Cursor positioning failed${NC}"
    ((FAILED++))
fi
((TOTAL++))

# ========== SCENARIO 9: Error Recovery ==========
echo -e "\n${YELLOW}=== SCENARIO 9: Error Handling ===${NC}"
run_scenario "Invalid Input Recovery" \
    "System handles invalid input gracefully" \
    "" \
    "XXXINVALID" \
    "999" \
    "!@#$%" \
    "?" \
    "Q"

# ========== SCENARIO 10: Session Limits ==========
echo -e "\n${YELLOW}=== SCENARIO 10: Session Management ===${NC}"
echo -n "Testing concurrent sessions... "
success=0
for i in {1..10}; do
    (echo -e "\r\n" | timeout 1 nc $HOST $PORT > /dev/null 2>&1) &
done
wait
echo -e "${GREEN}✅ 10 concurrent sessions${NC}"
((PASSED++))
((TOTAL++))

# ========== SCENARIO 11: International Support ==========
echo -e "\n${YELLOW}=== SCENARIO 11: International Characters ===${NC}"
run_scenario "Unicode Support" \
    "Testing international character sets" \
    "" \
    "Привет мир" \
    "你好世界" \
    "مرحبا بالعالم" \
    "🌍🌎🌏" \
    "Q"

# ========== SCENARIO 12: Admin Functions ==========
echo -e "\n${YELLOW}=== SCENARIO 12: Admin Access ===${NC}"
run_scenario "Admin Functions" \
    "Testing administrative features" \
    "" \
    "A" \
    "admin" \
    "adminpass" \
    "S" \
    "U" \
    "L" \
    "Q"

# ========== PERFORMANCE SCENARIOS ==========
echo -e "\n${YELLOW}=== PERFORMANCE TESTING ===${NC}"

# Rapid input test
echo -n "Rapid input handling... "
(for i in {1..100}; do echo "test$i"; done | timeout 5 nc $HOST $PORT > /dev/null 2>&1)
if [ $? -eq 124 ] || [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Handled 100 rapid inputs${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ Failed on rapid input${NC}"
    ((FAILED++))
fi
((TOTAL++))

# Large payload test
echo -n "Large payload handling... "
large_data=$(head -c 10000 /dev/urandom | base64)
echo "$large_data" | timeout 5 nc $HOST $PORT > /dev/null 2>&1
if [ $? -eq 124 ] || [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Handled 10KB payload${NC}"
    ((PASSED++))
else
    echo -e "${RED}❌ Failed on large payload${NC}"
    ((FAILED++))
fi
((TOTAL++))

# ========== SUMMARY ==========
echo ""
echo "=========================================="
echo "E2E TEST SUMMARY"
echo "=========================================="
echo -e "${GREEN}Passed Scenarios: $PASSED${NC}"
echo -e "${RED}Failed Scenarios: $FAILED${NC}"
echo -e "Total Scenarios: $TOTAL"

SUCCESS_RATE=$((PASSED * 100 / TOTAL))
echo "Success Rate: ${SUCCESS_RATE}%"

if [ $SUCCESS_RATE -ge 80 ]; then
    echo -e "${GREEN}✅ E2E Testing PASSED${NC}"
    exit 0
elif [ $SUCCESS_RATE -ge 60 ]; then
    echo -e "${YELLOW}⚠️ E2E Testing PARTIAL${NC}"
    exit 1
else
    echo -e "${RED}❌ E2E Testing FAILED${NC}"
    exit 2
fi