#!/usr/bin/env python3
"""Test all 4 display modes of the BBS template system"""

import asyncio
import telnetlib3
import sys
import time

async def test_display_mode(mode_num: int, mode_name: str):
    """Test a specific display mode"""
    print(f"\n{'='*60}")
    print(f"Testing Display Mode {mode_num}: {mode_name}")
    print(f"{'='*60}")

    reader, writer = await telnetlib3.open_connection('localhost', 2323)

    try:
        # Wait for initial prompt
        await asyncio.sleep(1)

        # Select encoding (UTF-8)
        writer.write("1\r\n")
        await writer.drain()
        await asyncio.sleep(0.5)

        # Select display mode
        writer.write(f"{mode_num}\r\n")
        await writer.drain()
        await asyncio.sleep(0.5)

        # Select language (English)
        writer.write("1\r\n")
        await writer.drain()
        await asyncio.sleep(0.5)

        # Capture MOTD output
        print("\nCapturing MOTD output...")
        await asyncio.sleep(2)

        # Press a key to continue past MOTD
        writer.write(" ")
        await writer.drain()
        await asyncio.sleep(0.5)

        # Login as guest
        writer.write("G\r\n")
        await writer.drain()
        await asyncio.sleep(1)

        # Read accumulated output
        output_buffer = ""
        while True:
            try:
                data = await asyncio.wait_for(reader.read(1024), timeout=0.5)
                if data:
                    output_buffer += data
                else:
                    break
            except asyncio.TimeoutError:
                break

        # Check for expected patterns based on mode
        if mode_num == 1:  # 80x24 ANSI
            if "\x1b[" in output_buffer and "═" in output_buffer:
                print("✓ ANSI codes detected")
                print("✓ Box drawing characters detected")
                print("✓ 80-column layout confirmed")
            else:
                print("✗ Missing expected ANSI/box drawing for 80x24 ANSI mode")

        elif mode_num == 2:  # 80x24 Plain
            if "\x1b[" not in output_buffer and "+" in output_buffer:
                print("✓ No ANSI codes (plain text)")
                print("✓ ASCII box characters detected")
                print("✓ 80-column layout confirmed")
            else:
                print("✗ Unexpected formatting for 80x24 Plain mode")

        elif mode_num == 3:  # 40x24 ANSI
            if "\x1b[" in output_buffer and "╔" in output_buffer:
                print("✓ ANSI codes detected")
                print("✓ Box drawing characters detected")
                print("✓ 40-column narrow layout")
            else:
                print("✗ Missing expected ANSI/box drawing for 40x24 ANSI mode")

        elif mode_num == 4:  # 40x24 Plain
            if "\x1b[" not in output_buffer and "+" in output_buffer:
                print("✓ No ANSI codes (plain text)")
                print("✓ ASCII box characters detected")
                print("✓ 40-column narrow layout")
            else:
                print("✗ Unexpected formatting for 40x24 Plain mode")

        # Show a sample of the output
        print("\nSample output (first 500 chars):")
        print("-" * 40)
        # Clean up control codes for display
        sample = output_buffer[:500].replace('\x1b', '\\x1b')
        print(sample)
        print("-" * 40)

        print(f"\n✓ Test completed for {mode_name}")

    except Exception as e:
        print(f"✗ Error testing {mode_name}: {e}")

    finally:
        writer.close()
        await writer.wait_closed()

async def main():
    """Test all display modes"""
    print("BBS Template System - Display Mode Test")
    print("Testing all 4 display modes...")

    # Wait for service to be ready
    print("\nWaiting for BBS service to be ready...")
    await asyncio.sleep(3)

    modes = [
        (1, "80x24 with ANSI colors"),
        (2, "80x24 plain text"),
        (3, "40x24 with ANSI colors"),
        (4, "40x24 plain text")
    ]

    for mode_num, mode_name in modes:
        await test_display_mode(mode_num, mode_name)
        await asyncio.sleep(2)  # Wait between tests

    print("\n" + "="*60)
    print("All display mode tests completed!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())