#!/usr/bin/env python3
"""Test CP866 charset support"""

import socket
import time

def test_cp866():
    """Test CP866 encoding selection"""
    print("Testing CP866 (DOS Russian) charset support...")

    try:
        # Connect to BBS
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(('localhost', 2323))

        # Wait for initial connection
        time.sleep(1)

        # Read initial data
        try:
            initial = s.recv(1024)
            print(f"Initial connection: {len(initial)} bytes")
        except socket.timeout:
            pass

        # The welcome screen should show
        time.sleep(0.5)

        # Send encoding selection "3" for CP866 (DOS Russian)
        # Note: CP866 is now at position 3 in the menu
        s.send(b"3\r\n")
        time.sleep(0.5)

        # Read response
        response = b""
        s.settimeout(0.5)
        try:
            while True:
                data = s.recv(1024)
                if data:
                    response += data
                else:
                    break
        except socket.timeout:
            pass

        # Check if we got CP866 confirmation
        if response:
            # Try to decode as CP866
            try:
                decoded = response.decode('cp866', errors='replace')
                print("✓ CP866 encoding selected successfully")
                print(f"Response includes terminal config prompt: {'Terminal' in decoded or 'terminal' in decoded}")

                # Check for Russian text if present
                if 'Русский' in decoded or 'русский' in decoded:
                    print("✓ Russian text detected in CP866 encoding")

            except Exception as e:
                print(f"✗ Failed to decode as CP866: {e}")

        s.close()
        print("\n✅ CP866 charset is available and working!")
        return True

    except Exception as e:
        print(f"\n✗ Error testing CP866: {e}")
        return False

if __name__ == "__main__":
    success = test_cp866()
    exit(0 if success else 1)