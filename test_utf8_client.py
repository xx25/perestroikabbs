#!/usr/bin/env python3
import socket
import time
import select

# Connect to the BBS using raw socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("localhost", 2323))
sock.setblocking(False)

def read_available(sock, timeout=1.0):
    """Read all available data from socket"""
    data = b""
    end_time = time.time() + timeout
    while time.time() < end_time:
        ready = select.select([sock], [], [], 0.1)
        if ready[0]:
            try:
                chunk = sock.recv(4096)
                if chunk:
                    data += chunk
                else:
                    break
            except BlockingIOError:
                pass
        else:
            if data:  # Got some data, can return
                break
    return data

# Wait for initial negotiation and prompt
time.sleep(0.5)
initial_data = read_available(sock, 2.0)

# Select UTF-8 encoding (option 1)
if b"Selection" in initial_data or b"encoding" in initial_data:
    sock.send(b"1\r\n")  # UTF-8
    time.sleep(0.3)
    read_available(sock, 1.0)  # Read response

    # Select English language (option 1)
    sock.send(b"1\r\n")  # English
    time.sleep(0.3)
    read_available(sock, 1.0)  # Read response

    # Keep default terminal size (just press enter)
    sock.send(b"\r\n")  # No override
    time.sleep(0.5)

# Now read the MOTD and menu
data = read_available(sock, 3.0)

# Also include initial data for analysis
data = initial_data + data

# Print raw bytes received
print("Raw bytes received (first 500):")
print(data[:500])
print()

# Check for UTF-8 box drawing characters or ANSI codes
if b'\xe2\x95\x94' in data:  # ╔
    print("Found UTF-8 box drawing character ╔")
elif b'\xe2\x95\x90' in data:  # ═
    print("Found UTF-8 box drawing character ═")
elif b'\xc9' in data or b'\xcd' in data:  # CP437 box drawing
    print("Found CP437 box drawing characters")
else:
    print("No UTF-8 box drawing characters found")

# Check for ANSI escape codes
if b'\x1b[' in data:
    print("Found ANSI escape sequences")
    if b'\x1b[2J' in data or b'\x1b[H' in data:
        print("Found clear screen ANSI codes (2J or H)")
else:
    print("No ANSI escape sequences found")

# Try to decode as UTF-8
print("\nDecoded as UTF-8:")
try:
    decoded = data.decode('utf-8', errors='replace')
    # Show first 20 lines
    lines = decoded.split('\n')
    for i, line in enumerate(lines[:20]):
        print(f"{i+1:3}: {line[:80]}")
except Exception as e:
    print(f"Error decoding: {e}")

# Check for BBS content
if b'BBS' in data or b'PERESTROIKA' in data:
    print("Found BBS in content")

sock.close()