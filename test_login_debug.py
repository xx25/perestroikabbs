#!/usr/bin/env python3
"""Debug BBS login flow"""
import socket
import time
import select

def test_bbs_interactive():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", 2323))
    sock.setblocking(False)

    def receive(timeout=2.0):
        data = b""
        end_time = time.time() + timeout
        while time.time() < end_time:
            ready = select.select([sock], [], [], 0.1)
            if ready[0]:
                try:
                    chunk = sock.recv(4096)
                    if chunk:
                        data += chunk
                except BlockingIOError:
                    pass
        return data

    print("=== BBS INTERACTION DEBUG ===\n")

    # Stage 1: Initial connection
    time.sleep(1)
    data = receive(3)
    print("Stage 1 - Initial prompt:")
    print(data.decode('utf-8', errors='replace')[:500])
    print("-" * 40)

    # Stage 2: Select encoding (1 for UTF-8)
    sock.send(b"1\r\n")
    time.sleep(0.5)
    data = receive(2)
    print("\nStage 2 - After encoding selection:")
    print(data.decode('utf-8', errors='replace')[:500])
    print("-" * 40)

    # Stage 3: Select language (1 for English)
    sock.send(b"1\r\n")
    time.sleep(0.5)
    data = receive(2)
    print("\nStage 3 - After language selection:")
    print(data.decode('utf-8', errors='replace')[:500])
    print("-" * 40)

    # Stage 4: Terminal size (just enter to keep default)
    sock.send(b"\r\n")
    time.sleep(1)
    data = receive(3)
    print("\nStage 4 - After terminal size (MOTD and menu):")
    decoded = data.decode('utf-8', errors='replace')
    print(decoded[:800])

    # Check what we got
    if "BBS" in decoded:
        print("\n✅ Found BBS in welcome screen")
    if "[L]" in decoded or "Login" in decoded:
        print("✅ Found Login option")
    if "[N]" in decoded or "Register" in decoded:
        print("✅ Found Register option")

    sock.close()

if __name__ == "__main__":
    test_bbs_interactive()