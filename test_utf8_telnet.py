#!/usr/bin/env python3
"""
Test client that properly handles telnet protocol negotiation and interacts with the BBS
"""
import socket
import time
import select

class TelnetClient:
    IAC = 255
    DONT = 254
    DO = 253
    WONT = 252
    WILL = 251

    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.sock.setblocking(False)

    def send_telnet_response(self, data):
        """Respond to telnet negotiation"""
        response = b""
        i = 0
        while i < len(data):
            if data[i] == self.IAC and i + 2 < len(data):
                cmd = data[i + 1]
                option = data[i + 2]

                # Respond to DO with WILL for binary mode
                if cmd == self.DO:
                    if option == 0:  # BINARY
                        response += bytes([self.IAC, self.WILL, option])
                    else:
                        response += bytes([self.IAC, self.WONT, option])
                # Respond to WILL with DO for binary mode
                elif cmd == self.WILL:
                    if option == 0:  # BINARY
                        response += bytes([self.IAC, self.DO, option])
                    else:
                        response += bytes([self.IAC, self.DONT, option])
                i += 3
            else:
                i += 1

        if response:
            self.sock.send(response)

    def read_with_timeout(self, timeout=2.0):
        """Read data and handle telnet negotiation"""
        data = b""
        text_data = b""
        end_time = time.time() + timeout

        while time.time() < end_time:
            ready = select.select([self.sock], [], [], 0.1)
            if ready[0]:
                try:
                    chunk = self.sock.recv(4096)
                    if chunk:
                        data += chunk
                        # Handle telnet commands
                        self.send_telnet_response(chunk)

                        # Extract text data (non-telnet commands)
                        i = 0
                        while i < len(chunk):
                            if chunk[i] == self.IAC and i + 2 < len(chunk):
                                i += 3  # Skip telnet command
                            elif chunk[i] != self.IAC:
                                text_data += bytes([chunk[i]])
                                i += 1
                            else:
                                i += 1
                except BlockingIOError:
                    pass

        return text_data

    def interact_with_bbs(self):
        """Interact with the BBS by selecting options"""
        # Initial negotiation
        time.sleep(0.5)
        initial = self.read_with_timeout(2.0)

        # Send UTF-8 selection (1)
        self.sock.send(b"1\r\n")
        time.sleep(0.3)
        encoding_resp = self.read_with_timeout(1.5)

        # Send English selection (1)
        self.sock.send(b"1\r\n")
        time.sleep(0.3)
        lang_resp = self.read_with_timeout(1.5)

        # Skip terminal size override (just enter)
        self.sock.send(b"\r\n")
        time.sleep(0.5)

        # Read MOTD and menu
        motd = self.read_with_timeout(3.0)

        # Combine all responses
        return initial + encoding_resp + lang_resp + motd

    def close(self):
        self.sock.close()

def main():
    client = TelnetClient("localhost", 2323)

    try:
        data = client.interact_with_bbs()

        print("Raw bytes received (first 500):")
        print(data[:500])
        print()

        # Check for UTF-8 box drawing characters
        if b'\xe2\x95\x94' in data:  # ╔
            print("Found UTF-8 box drawing character ╔")
        elif b'\xe2\x95\x90' in data:  # ═
            print("Found UTF-8 box drawing character ═")
        elif b'\xc9' in data or b'\xcd' in data:  # CP437
            print("Found CP437 box drawing characters")
        else:
            print("No box drawing characters found")

        # Check for ANSI escape codes
        if b'\x1b[' in data:
            print("Found ANSI escape sequences")
            if b'\x1b[2J' in data:
                print("Found clear screen ANSI code (2J)")
            if b'\x1b[H' in data:
                print("Found cursor home ANSI code (H)")
        else:
            print("No ANSI escape sequences found")

        # Check for BBS content
        if b'BBS' in data or b'PERESTROIKA' in data:
            print("Found BBS in content")
        else:
            print("BBS content not found")

        print("\nDecoded as UTF-8:")
        try:
            decoded = data.decode('utf-8', errors='replace')
            lines = decoded.split('\n')
            for i, line in enumerate(lines[:30]):
                if line.strip():
                    print(f"{i+1:3}: {line[:80]}")
        except Exception as e:
            print(f"Error decoding: {e}")

    finally:
        client.close()

if __name__ == "__main__":
    main()