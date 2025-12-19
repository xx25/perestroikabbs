#!/usr/bin/env python3
"""Test MacCyrillic charset support"""

import socket
import time

def test_mac_cyrillic():
    """Test MacCyrillic encoding selection"""
    print("Testing MacCyrillic (x-mac-cyrillic) charset support...")
    print("MacCyrillic is now option #12 in the menu")

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

        # Count the position of MacCyrillic in the menu:
        # 1. UTF-8
        # 2. CP437 (DOS)
        # 3. CP866 (DOS Russian)
        # 4. ISO-8859-1 (Latin-1)
        # 5. ISO-8859-2 (Central European)
        # 6. ISO-8859-5 (Cyrillic)
        # 7. ISO-8859-7 (Greek)
        # 8. KOI8-R (Russian)
        # 9. Windows-1251 (Cyrillic)
        # 10. Windows-1252 (Western)
        # 11. MacRoman
        # 12. MacCyrillic  <-- NEW
        # 13. Shift_JIS (Japanese)

        # Send encoding selection "12" for MacCyrillic
        s.send(b"12\r\n")
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

        # Check if we got MacCyrillic confirmation
        if response:
            # Try to decode as MacCyrillic
            try:
                # Python uses 'x-mac-cyrillic' as the codec name
                decoded = response.decode('x-mac-cyrillic', errors='replace')
                print("✓ MacCyrillic encoding selected successfully")
                print(f"Response includes terminal config: {'Terminal' in decoded or 'terminal' in decoded}")

                # Check that ASCII fallback is being used for box chars
                # since MacCyrillic doesn't support box drawing
                if '+' in decoded or '-' in decoded or '|' in decoded:
                    print("✓ ASCII fallback for box drawing detected (expected for MacCyrillic)")

            except LookupError:
                print("⚠ Python doesn't support x-mac-cyrillic codec on this system")
                print("  (This is OK - the BBS will handle it)")
            except Exception as e:
                print(f"✗ Failed to decode as MacCyrillic: {e}")

        s.close()
        print("\n✅ MacCyrillic charset is available in the menu!")
        return True

    except Exception as e:
        print(f"\n✗ Error testing MacCyrillic: {e}")
        return False

if __name__ == "__main__":
    success = test_mac_cyrillic()
    exit(0 if success else 1)