import asyncio
import hashlib
import struct
from enum import Enum
from pathlib import Path
from typing import Optional

from xmodem import XMODEM

from ..session import Session
from ..storage.repositories import FileRepository
from ..utils.logger import get_logger

logger = get_logger("transfers.xmodem")


class XModemMode(Enum):
    STANDARD = 128  # 128-byte blocks
    ONE_K = 1024   # 1024-byte blocks (XMODEM-1K)


class XModemProtocol:
    SOH = 0x01  # Start of header (128 bytes)
    STX = 0x02  # Start of header (1024 bytes)
    EOT = 0x04  # End of transmission
    ACK = 0x06  # Acknowledge
    NAK = 0x15  # Negative acknowledge
    CAN = 0x18  # Cancel
    SUB = 0x1A  # Substitute (padding)

    def __init__(self, session: Session):
        self.session = session
        self.file_repo = FileRepository()
        self.mode = XModemMode.STANDARD
        self.use_crc = False
        self.block_num = 1
        self.cancelled = False

    async def send_file(self, file_path: Path) -> bool:
        """Send a file using XMODEM protocol"""
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return False

        try:
            file_size = file_path.stat().st_size
            await self.session.writeline(f"\r\nStarting XMODEM send of {file_path.name} ({file_size} bytes)")
            await self.session.writeline("Start your XMODEM receive now...")

            # Wait for NAK or 'C' to start
            start_char = await self._wait_for_start()
            if not start_char:
                await self.session.writeline("\r\nTimeout waiting for receiver")
                return False

            self.use_crc = (start_char == ord('C'))

            with open(file_path, 'rb') as f:
                total_blocks = (file_size + self.mode.value - 1) // self.mode.value

                while True:
                    data = f.read(self.mode.value)
                    if not data:
                        break

                    # Pad last block if needed
                    if len(data) < self.mode.value:
                        data += bytes([self.SUB] * (self.mode.value - len(data)))

                    # Send block
                    if not await self._send_block(data):
                        await self.session.writeline("\r\nTransfer failed")
                        return False

                    # Progress indicator
                    if self.block_num % 10 == 0:
                        progress = (self.block_num * 100) // total_blocks
                        await self.session.write(f"\rProgress: {progress}%")

                    self.block_num += 1

                # Send EOT
                await self._send_eot()
                await self.session.writeline("\r\nTransfer completed successfully")
                return True

        except Exception as e:
            logger.error(f"XMODEM send error: {e}")
            await self.session.writeline(f"\r\nTransfer error: {e}")
            return False

    async def receive_file(self, save_path: Path, expected_size: Optional[int] = None) -> bool:
        """Receive a file using XMODEM protocol"""
        try:
            await self.session.writeline(f"\r\nStarting XMODEM receive to {save_path.name}")
            await self.session.writeline("Start your XMODEM send now...")

            # Send initial NAK or 'C' for CRC mode
            await self.session.write_raw(b'C' if self.use_crc else bytes([self.NAK]))

            received_data = bytearray()
            self.block_num = 1
            retries = 0
            max_retries = 10

            while retries < max_retries:
                # Read block header
                header = await self._read_with_timeout(1)
                if not header:
                    retries += 1
                    await self.session.write_raw(bytes([self.NAK]))
                    continue

                header_byte = header[0]

                # Check for EOT
                if header_byte == self.EOT:
                    await self.session.write_raw(bytes([self.ACK]))
                    break

                # Check for Cancel
                if header_byte == self.CAN:
                    await self.session.writeline("\r\nTransfer cancelled by sender")
                    return False

                # Determine block size
                if header_byte == self.SOH:
                    block_size = 128
                elif header_byte == self.STX:
                    block_size = 1024
                else:
                    retries += 1
                    await self.session.write_raw(bytes([self.NAK]))
                    continue

                # Read rest of block
                block_data = await self._receive_block(block_size)
                if block_data:
                    received_data.extend(block_data)
                    await self.session.write_raw(bytes([self.ACK]))
                    self.block_num += 1
                    retries = 0

                    # Progress indicator
                    if expected_size and len(received_data) > 0:
                        progress = (len(received_data) * 100) // expected_size
                        await self.session.write(f"\rProgress: {progress}%")
                else:
                    retries += 1
                    await self.session.write_raw(bytes([self.NAK]))

            if retries >= max_retries:
                await self.session.writeline("\r\nToo many errors, transfer aborted")
                return False

            # Remove padding from last block
            while received_data and received_data[-1] == self.SUB:
                received_data.pop()

            # Save file
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(received_data)

            await self.session.writeline(f"\r\nReceived {len(received_data)} bytes successfully")
            return True

        except Exception as e:
            logger.error(f"XMODEM receive error: {e}")
            await self.session.writeline(f"\r\nTransfer error: {e}")
            return False

    async def _wait_for_start(self, timeout: int = 60) -> Optional[int]:
        """Wait for NAK or 'C' from receiver"""
        for _ in range(timeout):
            data = await self._read_with_timeout(1)
            if data:
                if data[0] == self.NAK or data[0] == ord('C'):
                    return data[0]
        return None

    async def _send_block(self, data: bytes) -> bool:
        """Send a single XMODEM block"""
        # Build packet
        if len(data) == 128:
            packet = bytes([self.SOH])
        else:
            packet = bytes([self.STX])

        packet += bytes([self.block_num & 0xFF])
        packet += bytes([0xFF - (self.block_num & 0xFF)])
        packet += data

        # Calculate and add checksum/CRC
        if self.use_crc:
            crc = self._calculate_crc(data)
            packet += struct.pack('>H', crc)
        else:
            checksum = sum(data) & 0xFF
            packet += bytes([checksum])

        # Send packet and wait for ACK
        retries = 0
        while retries < 10:
            await self.session.write_raw(packet)

            response = await self._read_with_timeout(1)
            if response and response[0] == self.ACK:
                return True
            elif response and response[0] == self.CAN:
                self.cancelled = True
                return False

            retries += 1

        return False

    async def _receive_block(self, block_size: int) -> Optional[bytes]:
        """Receive and validate a single XMODEM block"""
        # Read block number and complement
        block_num = await self._read_with_timeout(1)
        if not block_num:
            return None

        block_num_comp = await self._read_with_timeout(1)
        if not block_num_comp:
            return None

        # Validate block number
        if (block_num[0] + block_num_comp[0]) & 0xFF != 0xFF:
            logger.warning("Block number validation failed")
            return None

        # Read data
        data = await self._read_with_timeout(block_size)
        if not data or len(data) != block_size:
            return None

        # Read and validate checksum/CRC
        if self.use_crc:
            crc_bytes = await self._read_with_timeout(2)
            if not crc_bytes or len(crc_bytes) != 2:
                return None
            received_crc = struct.unpack('>H', crc_bytes)[0]
            calculated_crc = self._calculate_crc(data)
            if received_crc != calculated_crc:
                logger.warning("CRC validation failed")
                return None
        else:
            checksum = await self._read_with_timeout(1)
            if not checksum:
                return None
            if (sum(data) & 0xFF) != checksum[0]:
                logger.warning("Checksum validation failed")
                return None

        return data

    async def _send_eot(self) -> bool:
        """Send End of Transmission"""
        retries = 0
        while retries < 10:
            await self.session.write_raw(bytes([self.EOT]))
            response = await self._read_with_timeout(1)
            if response and response[0] == self.ACK:
                return True
            retries += 1
        return False

    async def _read_with_timeout(self, size: int, timeout: float = 10.0) -> Optional[bytes]:
        """Read raw binary data with timeout"""
        return await self.session.read_raw(size, timeout)

    @staticmethod
    def _calculate_crc(data: bytes) -> int:
        """Calculate CRC16-CCITT"""
        crc = 0
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc = crc << 1
                crc &= 0xFFFF
        return crc