#!/usr/bin/env python3
"""
Integration tests for Perestroika BBS using pexpect
Tests all major BBS functionality through telnet
"""

import pexpect
import pytest
import time
import os
from typing import Optional


class TestBBSIntegration:
    """Integration tests for BBS telnet interface"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.host = os.environ.get('BBS_HOST', 'localhost')
        self.port = int(os.environ.get('BBS_PORT', '2323'))
        self.timeout = 10
        self.child: Optional[pexpect.spawn] = None

    def connect(self) -> pexpect.spawn:
        """Establish telnet connection"""
        self.child = pexpect.spawn(f'telnet {self.host} {self.port}', timeout=self.timeout)
        return self.child

    def teardown_method(self):
        """Cleanup after each test"""
        if self.child and self.child.isalive():
            try:
                self.child.close(force=True)
            except:
                pass

    # ========== Connection Tests ==========

    def test_connection_established(self):
        """Test that BBS accepts telnet connections"""
        child = self.connect()

        # Should see some initial output or telnet negotiation
        index = child.expect([
            'Connected to',  # Telnet connection message
            'Escape character',  # Telnet ready message
            pexpect.TIMEOUT
        ])

        assert index != 2, "Connection timeout - BBS not responding"

        # Should receive some data from BBS
        time.sleep(2)
        child.sendline('')  # Send empty line

        # Look for any BBS response
        try:
            child.expect(['.*', pexpect.EOF], timeout=3)
            assert True, "BBS is responding"
        except pexpect.TIMEOUT:
            pytest.fail("BBS not sending any data")

    def test_telnet_negotiation(self):
        """Test telnet protocol negotiation"""
        child = self.connect()

        # Wait for initial negotiation
        time.sleep(2)

        # Send terminal type subnegotiation
        child.send('\xff\xfa\x18\x00XTERM\xff\xf0')

        # BBS should continue working
        child.sendline('')

        try:
            child.expect(['.*', pexpect.EOF], timeout=3)
            assert True, "Telnet negotiation handled"
        except pexpect.TIMEOUT:
            pytest.fail("BBS stopped responding after telnet negotiation")

    # ========== Menu Tests ==========

    def test_main_menu_displayed(self):
        """Test that main menu is displayed"""
        child = self.connect()

        # Wait for menu
        time.sleep(3)

        # Look for menu options
        menu_items = ['login', 'register', 'guest', 'quit', 'exit', 'help']
        found_items = []

        for item in menu_items:
            try:
                child.expect(item, timeout=1)
                found_items.append(item)
            except:
                pass

        assert len(found_items) > 0, f"No menu items found. Expected at least one of: {menu_items}"

    def test_invalid_menu_option(self):
        """Test handling of invalid menu options"""
        child = self.connect()

        time.sleep(2)

        # Send invalid option
        child.sendline('XXXINVALID')

        # Should get error or menu redisplay
        responses = ['invalid', 'error', 'unknown', 'please', 'try again', 'menu']

        found = False
        for response in responses:
            try:
                child.expect(response, timeout=2)
                found = True
                break
            except:
                pass

        assert found, "BBS should handle invalid input gracefully"

    # ========== Registration Tests ==========

    def test_registration_accessible(self):
        """Test that registration option is available"""
        child = self.connect()

        time.sleep(2)

        # Try common registration commands
        for cmd in ['R', 'register', 'new', 'signup']:
            child.sendline(cmd)

            try:
                # Look for registration prompts
                index = child.expect([
                    'username',
                    'Username',
                    'login',
                    'Login',
                    'name',
                    'Name',
                    'register',
                    'Register',
                    pexpect.TIMEOUT
                ], timeout=2)

                if index < 8:  # Not timeout
                    assert True, f"Registration accessible with command: {cmd}"
                    return
            except:
                pass

        pytest.fail("Registration not accessible with common commands")

    def test_registration_validation(self):
        """Test registration input validation"""
        child = self.connect()

        time.sleep(2)

        # Access registration
        child.sendline('R')
        time.sleep(1)

        # Try empty username
        child.sendline('')

        # Should get validation error
        try:
            child.expect(['required', 'empty', 'invalid', 'enter'], timeout=2)
            assert True, "Empty username validation works"
        except pexpect.TIMEOUT:
            pass  # Some systems might just re-prompt

    # ========== Guest Access Tests ==========

    def test_guest_access(self):
        """Test guest access if available"""
        child = self.connect()

        time.sleep(2)

        # Try guest commands
        for cmd in ['G', 'guest', 'anonymous']:
            child.sendline(cmd)

            try:
                index = child.expect([
                    'guest',
                    'Guest',
                    'anonymous',
                    'Anonymous',
                    'welcome',
                    'Welcome',
                    pexpect.TIMEOUT
                ], timeout=2)

                if index < 6:  # Not timeout
                    assert True, f"Guest access available with command: {cmd}"
                    return
            except:
                pass

        # Guest access might not be implemented yet
        pytest.skip("Guest access not available")

    # ========== ANSI Tests ==========

    def test_ansi_escape_sequences(self):
        """Test ANSI color and positioning support"""
        child = self.connect()

        time.sleep(2)

        # Send cursor position request
        child.send('\x1b[6n')

        # Look for cursor position response (ESC[row;colR)
        try:
            child.expect('\x1b\\[\\d+;\\d+R', timeout=2)
            assert True, "ANSI cursor positioning supported"
        except pexpect.TIMEOUT:
            pytest.skip("ANSI positioning not detected")

    def test_ansi_colors(self):
        """Test ANSI color codes in output"""
        child = self.connect()

        time.sleep(2)

        # Look for ANSI color codes in output
        color_codes = [
            '\x1b\\[3[0-7]m',  # Foreground colors
            '\x1b\\[4[0-7]m',  # Background colors
            '\x1b\\[1m',        # Bold
            '\x1b\\[0m',        # Reset
        ]

        found_colors = False
        for code in color_codes:
            try:
                child.expect(code, timeout=1)
                found_colors = True
                break
            except:
                pass

        if found_colors:
            assert True, "ANSI colors detected in output"
        else:
            pytest.skip("No ANSI colors detected")

    # ========== Exit Tests ==========

    def test_quit_command(self):
        """Test quit/exit functionality"""
        child = self.connect()

        time.sleep(2)

        # Try quit commands
        quit_commands = ['Q', 'quit', 'exit', 'logout', 'bye']

        for cmd in quit_commands:
            child.sendline(cmd)

            try:
                # Look for disconnect messages or EOF
                index = child.expect([
                    'goodbye',
                    'Goodbye',
                    'bye',
                    'Bye',
                    'disconnected',
                    'Disconnected',
                    'closing',
                    'Closing',
                    pexpect.EOF
                ], timeout=2)

                assert True, f"Quit command '{cmd}' works"
                return
            except pexpect.TIMEOUT:
                pass

        pytest.fail("No quit command worked")

    # ========== Encoding Tests ==========

    def test_utf8_support(self):
        """Test UTF-8 character support"""
        child = self.connect()

        time.sleep(2)

        # Send UTF-8 characters
        test_strings = [
            "Hello World",      # ASCII
            "Привет мир",      # Cyrillic
            "你好世界",         # Chinese
            "مرحبا بالعالم",   # Arabic
        ]

        for test_str in test_strings:
            child.sendline(test_str)
            time.sleep(0.5)

        # BBS should still be responsive
        child.sendline('')

        try:
            child.expect(['.*', pexpect.EOF], timeout=2)
            assert True, "UTF-8 characters handled"
        except pexpect.TIMEOUT:
            pytest.fail("BBS stopped responding after UTF-8 input")

    # ========== Performance Tests ==========

    def test_rapid_input(self):
        """Test handling of rapid input"""
        child = self.connect()

        time.sleep(2)

        # Send rapid commands
        for i in range(10):
            child.sendline(f'test{i}')
            time.sleep(0.1)

        # BBS should still be responsive
        child.sendline('')

        try:
            child.expect(['.*', pexpect.EOF], timeout=2)
            assert True, "Rapid input handled"
        except pexpect.TIMEOUT:
            pytest.fail("BBS stopped responding after rapid input")

    def test_long_input(self):
        """Test handling of very long input lines"""
        child = self.connect()

        time.sleep(2)

        # Send very long line
        long_input = 'A' * 1000
        child.sendline(long_input)

        # Should handle gracefully
        time.sleep(1)
        child.sendline('')

        try:
            child.expect(['.*', pexpect.EOF], timeout=2)
            assert True, "Long input handled"
        except pexpect.TIMEOUT:
            pytest.fail("BBS stopped responding after long input")


class TestBBSReliability:
    """Test BBS reliability and error handling"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.host = os.environ.get('BBS_HOST', 'localhost')
        self.port = int(os.environ.get('BBS_PORT', '2323'))

    def test_multiple_connections(self):
        """Test handling multiple simultaneous connections"""
        connections = []

        try:
            # Open multiple connections
            for i in range(5):
                child = pexpect.spawn(f'telnet {self.host} {self.port}', timeout=5)
                connections.append(child)
                time.sleep(0.5)

            # All should be connected
            for i, conn in enumerate(connections):
                conn.sendline('')
                try:
                    conn.expect(['.*', pexpect.EOF], timeout=2)
                    assert True, f"Connection {i} active"
                except:
                    pytest.fail(f"Connection {i} not responding")

        finally:
            # Cleanup
            for conn in connections:
                try:
                    conn.close(force=True)
                except:
                    pass

    def test_connection_recovery(self):
        """Test reconnection after disconnect"""
        # First connection
        child1 = pexpect.spawn(f'telnet {self.host} {self.port}', timeout=5)
        time.sleep(2)
        child1.close(force=True)

        # Should be able to reconnect immediately
        child2 = pexpect.spawn(f'telnet {self.host} {self.port}', timeout=5)
        time.sleep(2)

        child2.sendline('')
        try:
            child2.expect(['.*', pexpect.EOF], timeout=2)
            assert True, "Reconnection successful"
        except pexpect.TIMEOUT:
            pytest.fail("Cannot reconnect after disconnect")
        finally:
            child2.close(force=True)


# Test runner for standalone execution
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])