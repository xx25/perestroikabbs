#!/bin/bash
# Comprehensive BBS Test Suite Runner
# Ensures all tests pass with 100% success rate

set -e  # Exit on first failure

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "PERESTROIKA BBS COMPREHENSIVE TEST SUITE"
echo "=========================================="
echo ""

TOTAL_PASSED=0
TOTAL_FAILED=0
ALL_TESTS_PASSED=true

# Function to run a test suite
run_test_suite() {
    local name="$1"
    local command="$2"

    echo -e "${BLUE}Running $name...${NC}"

    if timeout 60 bash -c "$command" > /tmp/test_output.log 2>&1; then
        # Check if output contains success indicators
        if grep -q "100%" /tmp/test_output.log || grep -q "All tests passed" /tmp/test_output.log || grep -q "E2E Testing PASSED" /tmp/test_output.log; then
            echo -e "${GREEN}✅ $name: PASSED${NC}"
            ((TOTAL_PASSED++))
        else
            echo -e "${RED}❌ $name: FAILED${NC}"
            echo "Output:"
            cat /tmp/test_output.log
            ((TOTAL_FAILED++))
            ALL_TESTS_PASSED=false
        fi
    else
        echo -e "${RED}❌ $name: FAILED (exit code $?)${NC}"
        echo "Output:"
        cat /tmp/test_output.log
        ((TOTAL_FAILED++))
        ALL_TESTS_PASSED=false
    fi
    echo ""
}

# Ensure BBS is running
echo -e "${YELLOW}Ensuring BBS is running...${NC}"
docker compose up -d bbs > /dev/null 2>&1
sleep 5

# Run all test suites
echo -e "${YELLOW}Starting test execution...${NC}"
echo ""

# 1. Simple connectivity tests
run_test_suite "Simple Connectivity Tests" "./tests/simple_test.sh"

# 2. End-to-End scenario tests
run_test_suite "E2E Scenario Tests" "./tests/test_e2e_scenarios.sh localhost 2323"

# 3. Quick functional test
echo -e "${BLUE}Running Quick Functional Test...${NC}"
if echo -e "\r\n1\r\n" | timeout 5 nc localhost 2323 2>/dev/null | grep -q "PERESTROIKA"; then
    echo -e "${GREEN}✅ Quick Functional Test: PASSED${NC}"
    ((TOTAL_PASSED++))
else
    echo -e "${RED}❌ Quick Functional Test: FAILED${NC}"
    ((TOTAL_FAILED++))
    ALL_TESTS_PASSED=false
fi
echo ""

# 4. UTF-8 encoding test
echo -e "${BLUE}Running UTF-8 Encoding Test...${NC}"
if python3 test_utf8_client.py 2>/dev/null | grep -q "Found UTF-8 box drawing character"; then
    echo -e "${GREEN}✅ UTF-8 Encoding Test: PASSED${NC}"
    ((TOTAL_PASSED++))
else
    echo -e "${RED}❌ UTF-8 Encoding Test: FAILED${NC}"
    ((TOTAL_FAILED++))
    ALL_TESTS_PASSED=false
fi
echo ""

# Summary
echo "=========================================="
echo "TEST SUITE SUMMARY"
echo "=========================================="
echo -e "${GREEN}Passed Test Suites: $TOTAL_PASSED${NC}"
echo -e "${RED}Failed Test Suites: $TOTAL_FAILED${NC}"

if [ "$ALL_TESTS_PASSED" = true ]; then
    echo ""
    echo -e "${GREEN}🎉 ALL TESTS PASSED WITH 100% SUCCESS RATE! 🎉${NC}"
    echo -e "${GREEN}The BBS is fully functional and ready for deployment.${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}⚠️  SOME TESTS FAILED ⚠️${NC}"
    echo -e "${RED}Please fix the issues before deployment.${NC}"
    exit 1
fi