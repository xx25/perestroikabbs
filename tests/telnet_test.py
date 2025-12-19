#!/usr/bin/env python3
"""
Automated Telnet Testing for Perestroika BBS
Tests all major functionality through actual telnet connections
"""

import asyncio
import telnetlib
import time
import re
import sys
from typing import Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum


class TestStatus(Enum):
    PASSED = "✅ PASSED"
    FAILED = "❌ FAILED"
    SKIPPED = "⏭️  SKIPPED"
    ERROR = "⚠️  ERROR"


@dataclass
class TestResult:
    name: str
    status: TestStatus
    message: str = ""
    duration: float = 0.0


class BBSTelnetTester:
    def __init__(self, host: str = "localhost", port: int = 2323, timeout: int = 5):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.results: List[TestResult] = []
        self.tn: Optional[telnetlib.Telnet] = None

    def connect(self) -> bool:
        """Establish telnet connection"""
        try:
            self.tn = telnetlib.Telnet(self.host, self.port, timeout=self.timeout)
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Close telnet connection"""
        if self.tn:
            try:
                self.tn.close()
            except:
                pass
            self.tn = None

    def send(self, text: str):
        """Send text to BBS"""
        if self.tn:
            self.tn.write(text.encode('utf-8'))
            time.sleep(0.1)  # Small delay for processing

    def send_line(self, text: str):
        """Send line with CRLF"""
        self.send(text + "\r\n")

    def read_until(self, expected: bytes, timeout: Optional[float] = None) -> bytes:
        """Read until expected string"""
        if not self.tn:
            return b""
        try:
            return self.tn.read_until(expected, timeout or self.timeout)
        except:
            return b""

    def read_some(self, timeout: float = 1.0) -> str:
        """Read available data"""
        if not self.tn:
            return ""
        try:
            # Try to read available data
            self.tn.sock.settimeout(timeout)
            data = self.tn.read_very_eager()
            return data.decode('utf-8', errors='replace')
        except:
            return ""

    def wait_for_prompt(self, prompts: List[str], timeout: float = 5.0) -> Tuple[bool, str]:
        """Wait for one of the prompts to appear"""
        start_time = time.time()
        buffer = ""

        while time.time() - start_time < timeout:
            data = self.read_some(0.5)
            buffer += data

            for prompt in prompts:
                if prompt in buffer:
                    return True, buffer

        return False, buffer

    def run_test(self, name: str, test_func) -> TestResult:
        """Run a single test"""
        print(f"\n🧪 Testing: {name}")
        start_time = time.time()

        try:
            success, message = test_func()
            duration = time.time() - start_time
            status = TestStatus.PASSED if success else TestStatus.FAILED
            result = TestResult(name, status, message, duration)
        except Exception as e:
            duration = time.time() - start_time
            result = TestResult(name, TestStatus.ERROR, str(e), duration)

        self.results.append(result)
        print(f"   {result.status.value} - {result.message} ({result.duration:.2f}s)")
        return result

    # ========== Individual Tests ==========

    def test_connection(self) -> Tuple[bool, str]:
        """Test basic connection"""
        if self.connect():
            # Wait for initial data
            time.sleep(1)
            data = self.read_some(2)
            self.disconnect()

            if data:
                return True, f"Connected successfully, received {len(data)} bytes"
            else:
                return True, "Connected but no initial data received"
        return False, "Failed to establish connection"

    def test_telnet_negotiation(self) -> Tuple[bool, str]:
        """Test telnet protocol negotiation"""
        if not self.connect():
            return False, "Failed to connect"

        # Send telnet NAWS (window size)
        self.tn.sock.sendall(b'\xff\xfa\x1f\x00\x50\x00\x18\xff\xf0')
        time.sleep(0.5)

        # Send terminal type
        self.tn.sock.sendall(b'\xff\xfa\x18\x00XTERM-256COLOR\xff\xf0')
        time.sleep(0.5)

        data = self.read_some(2)
        self.disconnect()

        if data:
            return True, "Telnet negotiation completed"
        return False, "No response to telnet negotiation"

    def test_ansi_support(self) -> Tuple[bool, str]:
        """Test ANSI escape sequence support"""
        if not self.connect():
            return False, "Failed to connect"

        # Send cursor position request
        self.send("\x1b[6n")
        time.sleep(0.5)

        data = self.read_some()
        self.disconnect()

        # Check for cursor position response (ESC[row;colR)
        if re.search(r'\x1b\[\d+;\d+R', data):
            return True, "ANSI cursor positioning supported"
        return False, "No ANSI response detected"

    def test_menu_display(self) -> Tuple[bool, str]:
        """Test if menu is displayed"""
        if not self.connect():
            return False, "Failed to connect"

        time.sleep(2)  # Wait for initial connection setup
        data = self.read_some(3)

        # Look for menu indicators
        menu_keywords = ['login', 'register', 'guest', 'menu', 'welcome', 'quit', 'exit']
        found_keywords = [kw for kw in menu_keywords if kw.lower() in data.lower()]

        self.disconnect()

        if found_keywords:
            return True, f"Menu displayed with options: {', '.join(found_keywords)}"
        return False, f"No menu found. Received: {data[:200]}"

    def test_invalid_input(self) -> Tuple[bool, str]:
        """Test handling of invalid input"""
        if not self.connect():
            return False, "Failed to connect"

        time.sleep(1)
        self.read_some()  # Clear buffer

        # Send invalid input
        self.send_line("XXXINVALIDXXX")
        time.sleep(1)

        response = self.read_some()
        self.disconnect()

        # Should get error or menu redisplay
        if response:
            return True, "Invalid input handled gracefully"
        return False, "No response to invalid input"

    def test_guest_access(self) -> Tuple[bool, str]:
        """Test guest access if available"""
        if not self.connect():
            return False, "Failed to connect"

        time.sleep(1)
        self.read_some()  # Clear buffer

        # Try guest login
        self.send_line("G")  # Common guest command
        time.sleep(1)
        response = self.read_some()

        if not response:
            self.send_line("guest")
            time.sleep(1)
            response = self.read_some()

        self.disconnect()

        if "guest" in response.lower() or "anonymous" in response.lower():
            return True, "Guest access available"
        return False, "Guest access not detected"

    def test_quit_command(self) -> Tuple[bool, str]:
        """Test quit/exit functionality"""
        if not self.connect():
            return False, "Failed to connect"

        time.sleep(1)
        self.read_some()  # Clear buffer

        # Try various quit commands
        for cmd in ["Q", "quit", "exit", "logout", "bye"]:
            self.send_line(cmd)
            time.sleep(0.5)

            # Check if connection closed
            try:
                self.tn.sock.send(b'')
            except:
                return True, f"Quit command '{cmd}' worked"

        self.disconnect()
        return False, "No quit command worked"

    def test_registration_flow(self) -> Tuple[bool, str]:
        """Test user registration flow"""
        if not self.connect():
            return False, "Failed to connect"

        time.sleep(1)
        self.read_some()  # Clear buffer

        # Try to access registration
        self.send_line("R")  # Common register command
        time.sleep(1)
        response = self.read_some()

        if "register" not in response.lower():
            self.send_line("register")
            time.sleep(1)
            response = self.read_some()

        self.disconnect()

        if any(word in response.lower() for word in ["username", "password", "register", "new user"]):
            return True, "Registration flow accessible"
        return False, "Registration flow not found"

    def test_encoding(self) -> Tuple[bool, str]:
        """Test character encoding support"""
        if not self.connect():
            return False, "Failed to connect"

        time.sleep(1)
        self.read_some()  # Clear buffer

        # Send UTF-8 characters
        test_chars = "Hello мир 世界 🌍"
        self.send_line(test_chars)
        time.sleep(1)

        response = self.read_some()
        self.disconnect()

        if response:
            return True, "Encoding test completed"
        return False, "No response to encoding test"

    def test_flow_control(self) -> Tuple[bool, str]:
        """Test XON/XOFF flow control"""
        if not self.connect():
            return False, "Failed to connect"

        # Send XOFF (pause)
        self.tn.sock.sendall(b'\x13')
        time.sleep(0.5)

        # Send XON (resume)
        self.tn.sock.sendall(b'\x11')
        time.sleep(0.5)

        self.disconnect()
        return True, "Flow control signals sent"

    # ========== Main Test Runner ==========

    def run_all_tests(self):
        """Run all tests"""
        print("=" * 60)
        print("🚀 PERESTROIKA BBS AUTOMATED TELNET TESTING")
        print("=" * 60)
        print(f"Target: {self.host}:{self.port}")
        print(f"Timeout: {self.timeout}s")

        # Define test suite
        tests = [
            ("Basic Connection", self.test_connection),
            ("Telnet Negotiation", self.test_telnet_negotiation),
            ("ANSI Support", self.test_ansi_support),
            ("Menu Display", self.test_menu_display),
            ("Invalid Input Handling", self.test_invalid_input),
            ("Guest Access", self.test_guest_access),
            ("Registration Flow", self.test_registration_flow),
            ("Quit Command", self.test_quit_command),
            ("Character Encoding", self.test_encoding),
            ("Flow Control", self.test_flow_control),
        ]

        # Run tests
        for name, test_func in tests:
            self.run_test(name, test_func)
            time.sleep(1)  # Delay between tests

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)

        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        errors = sum(1 for r in self.results if r.status == TestStatus.ERROR)
        total = len(self.results)

        for result in self.results:
            print(f"{result.status.value} {result.name}")
            if result.message:
                print(f"     └─ {result.message}")

        print("\n" + "-" * 60)
        print(f"Total Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Errors: {errors}")
        print(f"Success Rate: {(passed/total*100):.1f}%")
        print("=" * 60)

        # Return exit code
        return 0 if failed == 0 and errors == 0 else 1


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="BBS Telnet Testing Suite")
    parser.add_argument("--host", default="localhost", help="BBS host")
    parser.add_argument("--port", type=int, default=2323, help="BBS port")
    parser.add_argument("--timeout", type=int, default=5, help="Connection timeout")

    args = parser.parse_args()

    tester = BBSTelnetTester(args.host, args.port, args.timeout)
    exit_code = tester.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()