#!/usr/bin/env python3
"""Test login and access to BBS features"""
import socket
import time
import select

class BBSTestClient:
    def __init__(self, host="localhost", port=2323):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.sock.setblocking(False)

    def send(self, data):
        if isinstance(data, str):
            data = data.encode()
        self.sock.send(data)

    def receive(self, timeout=2.0):
        """Receive data with timeout"""
        data = b""
        end_time = time.time() + timeout
        while time.time() < end_time:
            ready = select.select([self.sock], [], [], 0.1)
            if ready[0]:
                try:
                    chunk = self.sock.recv(4096)
                    if chunk:
                        data += chunk
                except BlockingIOError:
                    pass
        return data

    def test_login_flow(self):
        print("Testing BBS Login Flow...")

        # Wait for initial prompt
        time.sleep(1)
        initial = self.receive(3)

        # Select UTF-8
        self.send(b"1\r\n")
        time.sleep(0.5)

        # Select English
        self.send(b"1\r\n")
        time.sleep(0.5)

        # Skip terminal override
        self.send(b"\r\n")
        time.sleep(0.5)

        # Read welcome and menu
        welcome = self.receive(3)

        # Try to login with demo credentials
        print("Attempting login with john/password...")
        self.send(b"L\r\n")  # Login option
        time.sleep(0.5)

        self.send(b"john\r\n")  # Username
        time.sleep(0.5)

        self.send(b"password\r\n")  # Password
        time.sleep(1)

        # Check if we get the main menu
        response = self.receive(3)

        # Check for features in response
        response_str = response.decode('utf-8', errors='ignore')

        features_found = []
        if "Message Boards" in response_str or "boards" in response_str.lower():
            features_found.append("Message Boards")
        if "Private Mail" in response_str or "mail" in response_str.lower():
            features_found.append("Private Mail")
        if "Chat" in response_str or "chat" in response_str.lower():
            features_found.append("Chat Rooms")
        if "File" in response_str or "file" in response_str.lower():
            features_found.append("File Library")

        return features_found

    def close(self):
        self.sock.close()

def main():
    client = BBSTestClient()
    try:
        features = client.test_login_flow()

        print("\n=== TEST RESULTS ===")
        if features:
            print("✅ Successfully logged in!")
            print("✅ Found BBS features:")
            for feature in features:
                print(f"   - {feature}")
        else:
            print("❌ Could not verify login or features")

    finally:
        client.close()

if __name__ == "__main__":
    main()