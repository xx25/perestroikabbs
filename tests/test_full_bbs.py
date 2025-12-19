#!/usr/bin/env python3
"""
Comprehensive BBS Functionality Testing Suite
Tests ALL features: users, boards, mail, chat, files, transfers, admin
"""

import asyncio
import os
import time
import random
import string
from typing import Optional, Dict, List
from dataclasses import dataclass
import subprocess
import json


@dataclass
class TestUser:
    """Test user data"""
    username: str
    password: str
    email: str
    is_admin: bool = False
    session_id: Optional[str] = None


class BBSComprehensiveTester:
    """Complete BBS functionality tester"""

    def __init__(self, host: str = "localhost", port: int = 2323):
        self.host = host
        self.port = port
        self.test_users: List[TestUser] = []
        self.test_results = {}
        self.current_test = None

    def generate_test_user(self) -> TestUser:
        """Generate random test user"""
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return TestUser(
            username=f"testuser_{suffix}",
            password=f"Pass_{suffix}!",
            email=f"test_{suffix}@example.com"
        )

    def telnet_command(self, commands: List[str], timeout: int = 5) -> str:
        """Execute telnet commands and return output"""
        cmd_str = '\n'.join(commands) + '\n'

        try:
            proc = subprocess.Popen(
                ['nc', self.host, str(self.port)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = proc.communicate(input=cmd_str, timeout=timeout)
            return stdout
        except subprocess.TimeoutExpired:
            proc.kill()
            return "TIMEOUT"
        except Exception as e:
            return f"ERROR: {e}"

    def log_result(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        self.test_results[test_name] = {
            'passed': passed,
            'details': details
        }

        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
        if details and not passed:
            print(f"  Details: {details}")

    # ========== USER MANAGEMENT TESTS ==========

    def test_user_registration(self) -> bool:
        """Test user registration flow"""
        print("\n🧪 Testing User Registration...")

        user = self.generate_test_user()

        # Try registration flow
        commands = [
            "",  # Initial connection
            "R",  # Register command
            user.username,
            user.password,
            user.password,  # Confirm password
            user.email,
            "Y"  # Confirm registration
        ]

        output = self.telnet_command(commands)

        # Check for success indicators
        success_indicators = ['registered', 'success', 'welcome', 'created']
        found = any(indicator in output.lower() for indicator in success_indicators)

        if found:
            self.test_users.append(user)

        self.log_result("User Registration", found, output[:200])
        return found

    def test_user_login(self) -> bool:
        """Test user login"""
        print("\n🧪 Testing User Login...")

        if not self.test_users:
            # Create a test user first
            self.test_user_registration()

        if not self.test_users:
            self.log_result("User Login", False, "No test users available")
            return False

        user = self.test_users[0]

        commands = [
            "",
            "L",  # Login command
            user.username,
            user.password
        ]

        output = self.telnet_command(commands)

        success = 'welcome' in output.lower() or 'logged' in output.lower()
        self.log_result("User Login", success, output[:200])
        return success

    def test_user_logout(self) -> bool:
        """Test user logout"""
        print("\n🧪 Testing User Logout...")

        commands = [
            "",
            "L",  # Login first
            "testuser",
            "testpass",
            "X",  # Logout/exit
        ]

        output = self.telnet_command(commands, timeout=3)

        success = 'goodbye' in output.lower() or 'logout' in output.lower() or output == ""
        self.log_result("User Logout", success, output[:200])
        return success

    def test_password_change(self) -> bool:
        """Test password change functionality"""
        print("\n🧪 Testing Password Change...")

        commands = [
            "",
            "L",
            "testuser",
            "oldpass",
            "P",  # Profile/Password
            "C",  # Change password
            "oldpass",
            "newpass123",
            "newpass123"
        ]

        output = self.telnet_command(commands)

        success = 'changed' in output.lower() or 'updated' in output.lower()
        self.log_result("Password Change", success, output[:200])
        return success

    # ========== MESSAGE BOARD TESTS ==========

    def test_board_list(self) -> bool:
        """Test listing message boards"""
        print("\n🧪 Testing Board List...")

        commands = [
            "",
            "B",  # Boards menu
            "L"   # List boards
        ]

        output = self.telnet_command(commands)

        success = 'board' in output.lower() or 'forum' in output.lower()
        self.log_result("Board List", success, output[:200])
        return success

    def test_post_message(self) -> bool:
        """Test posting a message"""
        print("\n🧪 Testing Post Message...")

        commands = [
            "",
            "B",  # Boards
            "1",  # Select first board
            "P",  # Post
            "Test Subject",
            "This is a test message body.",
            "Y"   # Confirm post
        ]

        output = self.telnet_command(commands)

        success = 'posted' in output.lower() or 'saved' in output.lower()
        self.log_result("Post Message", success, output[:200])
        return success

    def test_read_messages(self) -> bool:
        """Test reading messages"""
        print("\n🧪 Testing Read Messages...")

        commands = [
            "",
            "B",  # Boards
            "1",  # Select board
            "R",  # Read messages
            "1"   # Read first message
        ]

        output = self.telnet_command(commands)

        success = 'subject' in output.lower() or 'from' in output.lower()
        self.log_result("Read Messages", success, output[:200])
        return success

    def test_reply_message(self) -> bool:
        """Test replying to a message"""
        print("\n🧪 Testing Reply to Message...")

        commands = [
            "",
            "B",
            "1",
            "R",  # Read
            "1",  # First message
            "R",  # Reply
            "This is a test reply",
            "Y"
        ]

        output = self.telnet_command(commands)

        success = 'reply' in output.lower() or 'posted' in output.lower()
        self.log_result("Reply Message", success, output[:200])
        return success

    # ========== MAIL SYSTEM TESTS ==========

    def test_send_mail(self) -> bool:
        """Test sending private mail"""
        print("\n🧪 Testing Send Mail...")

        commands = [
            "",
            "M",  # Mail menu
            "S",  # Send mail
            "sysop",  # Recipient
            "Test Mail Subject",
            "This is a test mail message.",
            "Y"  # Send
        ]

        output = self.telnet_command(commands)

        success = 'sent' in output.lower() or 'delivered' in output.lower()
        self.log_result("Send Mail", success, output[:200])
        return success

    def test_read_mail(self) -> bool:
        """Test reading mail"""
        print("\n🧪 Testing Read Mail...")

        commands = [
            "",
            "M",  # Mail
            "R",  # Read mail
            "1"   # First message
        ]

        output = self.telnet_command(commands)

        success = 'from' in output.lower() or 'subject' in output.lower()
        self.log_result("Read Mail", success, output[:200])
        return success

    def test_delete_mail(self) -> bool:
        """Test deleting mail"""
        print("\n🧪 Testing Delete Mail...")

        commands = [
            "",
            "M",
            "R",
            "1",
            "D",  # Delete
            "Y"   # Confirm
        ]

        output = self.telnet_command(commands)

        success = 'deleted' in output.lower() or 'removed' in output.lower()
        self.log_result("Delete Mail", success, output[:200])
        return success

    # ========== CHAT SYSTEM TESTS ==========

    def test_chat_rooms(self) -> bool:
        """Test chat room listing"""
        print("\n🧪 Testing Chat Rooms...")

        commands = [
            "",
            "C",  # Chat
            "L"   # List rooms
        ]

        output = self.telnet_command(commands)

        success = 'room' in output.lower() or 'chat' in output.lower()
        self.log_result("Chat Rooms", success, output[:200])
        return success

    def test_join_chat(self) -> bool:
        """Test joining chat room"""
        print("\n🧪 Testing Join Chat...")

        commands = [
            "",
            "C",  # Chat
            "J",  # Join
            "main",  # Room name
            "Hello everyone!",  # Message
            "/quit"  # Leave chat
        ]

        output = self.telnet_command(commands)

        success = 'joined' in output.lower() or 'entering' in output.lower()
        self.log_result("Join Chat", success, output[:200])
        return success

    def test_private_message(self) -> bool:
        """Test private messaging in chat"""
        print("\n🧪 Testing Private Message...")

        commands = [
            "",
            "C",
            "J",
            "main",
            "/whisper sysop Hello privately",
            "/quit"
        ]

        output = self.telnet_command(commands)

        success = 'whisper' in output.lower() or 'private' in output.lower()
        self.log_result("Private Message", success, output[:200])
        return success

    # ========== FILE SYSTEM TESTS ==========

    def test_file_listing(self) -> bool:
        """Test file area listing"""
        print("\n🧪 Testing File Listing...")

        commands = [
            "",
            "F",  # Files
            "L"   # List files
        ]

        output = self.telnet_command(commands)

        success = 'file' in output.lower() or 'download' in output.lower()
        self.log_result("File Listing", success, output[:200])
        return success

    def test_file_search(self) -> bool:
        """Test file search"""
        print("\n🧪 Testing File Search...")

        commands = [
            "",
            "F",
            "S",  # Search
            "*.txt"  # Search pattern
        ]

        output = self.telnet_command(commands)

        success = 'search' in output.lower() or 'found' in output.lower()
        self.log_result("File Search", success, output[:200])
        return success

    def test_file_info(self) -> bool:
        """Test file information display"""
        print("\n🧪 Testing File Info...")

        commands = [
            "",
            "F",
            "I",  # Info
            "1"   # First file
        ]

        output = self.telnet_command(commands)

        success = 'size' in output.lower() or 'description' in output.lower()
        self.log_result("File Info", success, output[:200])
        return success

    # ========== TRANSFER PROTOCOL TESTS ==========

    def test_xmodem_init(self) -> bool:
        """Test XMODEM transfer initialization"""
        print("\n🧪 Testing XMODEM Init...")

        commands = [
            "",
            "F",
            "D",  # Download
            "1",  # File ID
            "X"   # XMODEM
        ]

        output = self.telnet_command(commands, timeout=3)

        # Look for XMODEM NAK or SOH
        success = '\x15' in output or '\x01' in output or 'xmodem' in output.lower()
        self.log_result("XMODEM Init", success, "Protocol initialized" if success else "No XMODEM response")
        return success

    def test_zmodem_init(self) -> bool:
        """Test ZMODEM transfer initialization"""
        print("\n🧪 Testing ZMODEM Init...")

        commands = [
            "",
            "F",
            "D",
            "1",
            "Z"  # ZMODEM
        ]

        output = self.telnet_command(commands, timeout=3)

        # Look for ZMODEM header
        success = 'rz' in output.lower() or '*B' in output
        self.log_result("ZMODEM Init", success, "Protocol initialized" if success else "No ZMODEM response")
        return success

    def test_kermit_init(self) -> bool:
        """Test Kermit transfer initialization"""
        print("\n🧪 Testing Kermit Init...")

        commands = [
            "",
            "F",
            "D",
            "1",
            "K"  # Kermit
        ]

        output = self.telnet_command(commands, timeout=3)

        success = 'kermit' in output.lower()
        self.log_result("Kermit Init", success, "Protocol initialized" if success else "No Kermit response")
        return success

    # ========== MENU NAVIGATION TESTS ==========

    def test_main_menu(self) -> bool:
        """Test main menu display"""
        print("\n🧪 Testing Main Menu...")

        commands = ["", "?"]  # Help/menu

        output = self.telnet_command(commands)

        # Check for menu items
        menu_items = ['board', 'mail', 'chat', 'file', 'user', 'quit']
        found = sum(1 for item in menu_items if item in output.lower())

        success = found >= 3
        self.log_result("Main Menu", success, f"Found {found}/{len(menu_items)} menu items")
        return success

    def test_help_system(self) -> bool:
        """Test help system"""
        print("\n🧪 Testing Help System...")

        commands = [
            "",
            "H",  # Help
        ]

        output = self.telnet_command(commands)

        success = 'help' in output.lower() or 'commands' in output.lower()
        self.log_result("Help System", success, output[:200])
        return success

    def test_user_profile(self) -> bool:
        """Test user profile viewing"""
        print("\n🧪 Testing User Profile...")

        commands = [
            "",
            "U",  # User menu
            "P"   # Profile
        ]

        output = self.telnet_command(commands)

        success = 'profile' in output.lower() or 'user' in output.lower()
        self.log_result("User Profile", success, output[:200])
        return success

    def test_who_online(self) -> bool:
        """Test who's online listing"""
        print("\n🧪 Testing Who's Online...")

        commands = [
            "",
            "W"  # Who's online
        ]

        output = self.telnet_command(commands)

        success = 'online' in output.lower() or 'users' in output.lower()
        self.log_result("Who's Online", success, output[:200])
        return success

    # ========== ADMIN TESTS ==========

    def test_admin_access(self) -> bool:
        """Test admin menu access"""
        print("\n🧪 Testing Admin Access...")

        commands = [
            "",
            "A"  # Admin
        ]

        output = self.telnet_command(commands)

        # Should require auth or show admin menu
        success = 'admin' in output.lower() or 'denied' in output.lower()
        self.log_result("Admin Access", success, output[:200])
        return success

    def test_system_stats(self) -> bool:
        """Test system statistics"""
        print("\n🧪 Testing System Stats...")

        commands = [
            "",
            "S",  # Stats
        ]

        output = self.telnet_command(commands)

        success = 'users' in output.lower() or 'posts' in output.lower() or 'stats' in output.lower()
        self.log_result("System Stats", success, output[:200])
        return success

    # ========== ANSI/GRAPHICS TESTS ==========

    def test_ansi_art(self) -> bool:
        """Test ANSI art display"""
        print("\n🧪 Testing ANSI Art...")

        commands = [
            "",
            "G"  # Graphics/Gallery
        ]

        output = self.telnet_command(commands)

        # Check for ANSI escape codes
        success = '\x1b[' in output
        self.log_result("ANSI Art", success, "ANSI codes detected" if success else "No ANSI codes")
        return success

    def test_color_support(self) -> bool:
        """Test color support"""
        print("\n🧪 Testing Color Support...")

        commands = [""]

        output = self.telnet_command(commands)

        # Check for color codes
        color_codes = ['\x1b[31m', '\x1b[32m', '\x1b[33m', '\x1b[34m']
        found = any(code in output for code in color_codes)

        self.log_result("Color Support", found, "Colors detected" if found else "No colors")
        return found

    # ========== ENCODING TESTS ==========

    def test_utf8_handling(self) -> bool:
        """Test UTF-8 character handling"""
        print("\n🧪 Testing UTF-8 Handling...")

        test_strings = [
            "Привет мир",  # Cyrillic
            "你好世界",     # Chinese
            "مرحبا",       # Arabic
            "🌍🌎🌏"       # Emoji
        ]

        for test_str in test_strings:
            commands = ["", test_str]
            output = self.telnet_command(commands, timeout=2)

            if "error" in output.lower():
                self.log_result(f"UTF-8: {test_str[:10]}", False, "Error handling UTF-8")
                return False

        self.log_result("UTF-8 Handling", True, "All UTF-8 tests passed")
        return True

    # ========== SESSION TESTS ==========

    def test_idle_timeout(self) -> bool:
        """Test idle timeout handling"""
        print("\n🧪 Testing Idle Timeout...")

        # Connect and wait
        commands = [""]
        output = self.telnet_command(commands, timeout=15)

        # Should get timeout warning or disconnect
        success = 'timeout' in output.lower() or 'idle' in output.lower() or output == ""
        self.log_result("Idle Timeout", success, "Timeout handled" if success else "No timeout")
        return success

    def test_concurrent_sessions(self) -> bool:
        """Test multiple concurrent sessions"""
        print("\n🧪 Testing Concurrent Sessions...")

        import threading
        results = []

        def connect():
            output = self.telnet_command(["", "W"], timeout=3)
            results.append('online' in output.lower())

        # Start 5 concurrent connections
        threads = []
        for _ in range(5):
            t = threading.Thread(target=connect)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        success = all(results) if results else False
        self.log_result("Concurrent Sessions", success, f"{sum(results)}/5 successful")
        return success

    # ========== MAIN TEST RUNNER ==========

    def run_all_tests(self):
        """Run all BBS functionality tests"""
        print("=" * 60)
        print("🚀 COMPREHENSIVE BBS FUNCTIONALITY TESTING")
        print("=" * 60)
        print(f"Target: {self.host}:{self.port}")
        print()

        test_categories = {
            "USER MANAGEMENT": [
                self.test_user_registration,
                self.test_user_login,
                self.test_user_logout,
                self.test_password_change,
                self.test_user_profile,
            ],
            "MESSAGE BOARDS": [
                self.test_board_list,
                self.test_post_message,
                self.test_read_messages,
                self.test_reply_message,
            ],
            "MAIL SYSTEM": [
                self.test_send_mail,
                self.test_read_mail,
                self.test_delete_mail,
            ],
            "CHAT SYSTEM": [
                self.test_chat_rooms,
                self.test_join_chat,
                self.test_private_message,
            ],
            "FILE SYSTEM": [
                self.test_file_listing,
                self.test_file_search,
                self.test_file_info,
            ],
            "TRANSFER PROTOCOLS": [
                self.test_xmodem_init,
                self.test_zmodem_init,
                self.test_kermit_init,
            ],
            "MENU & NAVIGATION": [
                self.test_main_menu,
                self.test_help_system,
                self.test_who_online,
            ],
            "ADMIN FUNCTIONS": [
                self.test_admin_access,
                self.test_system_stats,
            ],
            "DISPLAY & GRAPHICS": [
                self.test_ansi_art,
                self.test_color_support,
            ],
            "ENCODING & I18N": [
                self.test_utf8_handling,
            ],
            "SESSION MANAGEMENT": [
                self.test_idle_timeout,
                self.test_concurrent_sessions,
            ]
        }

        category_results = {}

        for category, tests in test_categories.items():
            print(f"\n{'=' * 40}")
            print(f"📂 {category}")
            print(f"{'=' * 40}")

            passed = 0
            total = len(tests)

            for test_func in tests:
                try:
                    if test_func():
                        passed += 1
                    time.sleep(1)  # Delay between tests
                except Exception as e:
                    print(f"  ⚠️ Test error: {e}")
                    self.log_result(test_func.__name__, False, str(e))

            category_results[category] = (passed, total)

        # Print summary
        self.print_summary(category_results)

        return self.test_results

    def print_summary(self, category_results):
        """Print comprehensive test summary"""
        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE TEST RESULTS")
        print("=" * 60)

        total_passed = 0
        total_tests = 0

        for category, (passed, total) in category_results.items():
            total_passed += passed
            total_tests += total

            percentage = (passed / total * 100) if total > 0 else 0

            # Color based on pass rate
            if percentage == 100:
                status = "✅"
            elif percentage >= 70:
                status = "🟡"
            else:
                status = "❌"

            print(f"{status} {category}: {passed}/{total} ({percentage:.0f}%)")

        print("-" * 60)

        overall_percentage = (total_passed / total_tests * 100) if total_tests > 0 else 0

        print(f"\n📈 OVERALL: {total_passed}/{total_tests} tests passed ({overall_percentage:.1f}%)")

        if overall_percentage == 100:
            print("🎉 PERFECT! All tests passed!")
        elif overall_percentage >= 80:
            print("✅ Good coverage, most features working")
        elif overall_percentage >= 60:
            print("🟡 Acceptable, but needs improvement")
        else:
            print("❌ Many features need attention")

        # List failed tests
        failed = [name for name, result in self.test_results.items() if not result['passed']]
        if failed:
            print(f"\n⚠️ Failed Tests ({len(failed)}):")
            for test in failed[:10]:  # Show first 10
                print(f"  - {test}")

        print("=" * 60)


def main():
    """Main test runner"""
    import argparse

    parser = argparse.ArgumentParser(description="Comprehensive BBS Testing")
    parser.add_argument("--host", default="localhost", help="BBS host")
    parser.add_argument("--port", type=int, default=2323, help="BBS port")
    parser.add_argument("--json", action="store_true", help="Output JSON results")

    args = parser.parse_args()

    tester = BBSComprehensiveTester(args.host, args.port)
    results = tester.run_all_tests()

    if args.json:
        print(json.dumps(results, indent=2))

    # Return exit code based on results
    passed = sum(1 for r in results.values() if r['passed'])
    return 0 if passed > len(results) * 0.8 else 1


if __name__ == "__main__":
    exit(main())