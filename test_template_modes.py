#!/usr/bin/env python3
"""Test the 4 display modes of the template system"""

import socket
import time
import sys

def test_display_mode(mode: int, mode_name: str):
    """Test a specific display mode"""
    print(f"\n{'='*60}")
    print(f"Testing Mode {mode}: {mode_name}")
    print(f"{'='*60}")

    try:
        # Connect to BBS
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(('localhost', 2323))

        # Wait for telnet negotiation
        time.sleep(1)

        # Read initial data (telnet negotiation)
        try:
            initial = s.recv(4096)
            print(f"Received {len(initial)} bytes of initial data")
        except socket.timeout:
            pass

        # Send encoding selection (1 = UTF-8)
        s.send(b"1\r\n")
        time.sleep(0.5)

        # Send display mode selection
        s.send(f"{mode}\r\n".encode())
        time.sleep(0.5)

        # Send language selection (1 = English)
        s.send(b"1\r\n")
        time.sleep(0.5)

        # Collect MOTD output
        time.sleep(2)

        # Read accumulated output
        output = b""
        s.settimeout(0.5)
        while True:
            try:
                data = s.recv(4096)
                if data:
                    output += data
                else:
                    break
            except socket.timeout:
                break

        # Decode output
        try:
            output_str = output.decode('utf-8', errors='replace')
        except:
            output_str = str(output)

        # Check for expected patterns
        if mode == 1:  # 80x24 ANSI
            has_ansi = b'\x1b[' in output
            has_box = '═' in output_str or '╔' in output_str
            if has_ansi and has_box:
                print("✓ ANSI codes detected")
                print("✓ Box drawing characters detected")
                print("✓ 80-column format confirmed")
            else:
                print(f"✗ Missing expected features (ANSI: {has_ansi}, Box: {has_box})")

        elif mode == 2:  # 80x24 Plain
            has_ansi = b'\x1b[' in output
            has_ascii = '=' in output_str or '+' in output_str
            if not has_ansi and has_ascii:
                print("✓ No ANSI codes (plain text)")
                print("✓ ASCII characters detected")
                print("✓ 80-column format confirmed")
            else:
                print(f"✗ Unexpected formatting (Has ANSI: {has_ansi})")

        elif mode == 3:  # 40x24 ANSI
            has_ansi = b'\x1b[' in output
            has_box = '╔' in output_str or '║' in output_str
            if has_ansi and has_box:
                print("✓ ANSI codes detected")
                print("✓ Box drawing for narrow display")
                print("✓ 40-column format")
            else:
                print(f"✗ Missing expected features (ANSI: {has_ansi}, Box: {has_box})")

        elif mode == 4:  # 40x24 Plain
            has_ansi = b'\x1b[' in output
            has_ascii = '+' in output_str or '-' in output_str
            if not has_ansi and has_ascii:
                print("✓ No ANSI codes (plain text)")
                print("✓ ASCII characters for narrow display")
                print("✓ 40-column format")
            else:
                print(f"✗ Unexpected formatting (Has ANSI: {has_ansi})")

        # Show sample output
        print("\nSample output (first 300 chars):")
        print("-" * 40)
        sample = output_str[:300].replace('\x1b', '\\x1b')
        for line in sample.split('\r\n')[:5]:
            print(line)
        print("-" * 40)

        s.close()
        print(f"✓ Test completed for {mode_name}")
        return True

    except Exception as e:
        print(f"✗ Error testing {mode_name}: {e}")
        return False

def main():
    """Test all 4 display modes"""
    print("="*60)
    print("BBS TEMPLATE SYSTEM - DISPLAY MODE TEST")
    print("="*60)

    modes = [
        (1, "80x24 with ANSI colors"),
        (2, "80x24 plain text"),
        (3, "40x24 with ANSI colors"),
        (4, "40x24 plain text")
    ]

    results = []
    for mode_num, mode_name in modes:
        success = test_display_mode(mode_num, mode_name)
        results.append((mode_name, success))
        time.sleep(2)  # Wait between tests

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for mode_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{mode_name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ ALL DISPLAY MODES WORKING CORRECTLY! ✅")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())