import asyncio
import os
import pty
from pathlib import Path
from typing import Optional

from ..session import Session
from ..utils.config import get_config
from ..utils.logger import get_logger

logger = get_logger("transfers.kermit")


class KermitTransfer:
    """Kermit file transfer using external C-Kermit binary via PTY"""

    def __init__(self, session: Session):
        self.session = session
        self.config = get_config().transfers
        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None
        self.process: Optional[asyncio.subprocess.Process] = None

    async def send_file(self, file_path: Path) -> bool:
        """Send a file using Kermit protocol"""
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            await self.session.writeline(f"\r\nError: File {file_path.name} not found")
            return False

        if not Path(self.config.ckermit_path).exists():
            logger.error("kermit binary not found")
            await self.session.writeline("\r\nError: Kermit not available on this system")
            return False

        try:
            # Sandbox check
            download_root = Path(self.config.download_root).resolve()
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(download_root)):
                logger.warning(f"Attempted to send file outside download root: {file_path}")
                await self.session.writeline("\r\nError: Access denied")
                return False

            await self.session.writeline(f"\r\nStarting Kermit send of {file_path.name}")
            await self.session.writeline(f"File size: {file_path.stat().st_size} bytes")
            await self.session.writeline("Start your Kermit receive now...")
            await asyncio.sleep(1)

            # Create PTY
            self.master_fd, self.slave_fd = pty.openpty()

            # Create Kermit script for sending
            kermit_script = f"""
set file type binary
set transfer display none
set protocol kermit
set send packet-length 1000
set window 4
set file incomplete keep
send {file_path}
exit
"""
            script_path = Path("/tmp/kermit_send.tmp")
            script_path.write_text(kermit_script)

            # Start kermit process
            self.process = await asyncio.create_subprocess_exec(
                self.config.ckermit_path,
                "-C",  # Command mode
                f"take {script_path}",
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd
            )

            # Close slave FD in parent process
            os.close(self.slave_fd)
            self.slave_fd = None

            # Set non-blocking mode
            import fcntl
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            # Pump data between PTY and telnet session
            success = await self._pump_data()

            # Clean up script file
            try:
                script_path.unlink()
            except:
                pass

            # Wait for process to complete
            await self.process.wait()

            if self.process.returncode == 0:
                await self.session.writeline("\r\nKermit transfer completed successfully")
                return True
            else:
                await self.session.writeline(f"\r\nKermit transfer failed (code: {self.process.returncode})")
                return False

        except Exception as e:
            logger.error(f"Kermit send error: {e}")
            await self.session.writeline(f"\r\nTransfer error: {e}")
            return False
        finally:
            await self._cleanup()

    async def receive_file(self, save_dir: Path) -> bool:
        """Receive a file using Kermit protocol"""
        if not Path(self.config.ckermit_path).exists():
            logger.error("kermit binary not found")
            await self.session.writeline("\r\nError: Kermit not available on this system")
            return False

        try:
            # Ensure upload directory exists and is sandboxed
            upload_root = Path(self.config.upload_root).resolve()
            save_dir = save_dir.resolve()

            if not str(save_dir).startswith(str(upload_root)):
                logger.warning(f"Attempted to save file outside upload root: {save_dir}")
                await self.session.writeline("\r\nError: Access denied")
                return False

            save_dir.mkdir(parents=True, exist_ok=True)

            await self.session.writeline("\r\nStarting Kermit receive")
            await self.session.writeline(f"Files will be saved to: {save_dir}")
            await self.session.writeline("Start your Kermit send now...")
            await asyncio.sleep(1)

            # Create PTY
            self.master_fd, self.slave_fd = pty.openpty()

            # Create Kermit script for receiving
            kermit_script = f"""
set file type binary
set transfer display none
set protocol kermit
set receive packet-length 1000
set window 4
set file incomplete keep
cd {save_dir}
receive
exit
"""
            script_path = Path("/tmp/kermit_receive.tmp")
            script_path.write_text(kermit_script)

            # Start kermit process
            self.process = await asyncio.create_subprocess_exec(
                self.config.ckermit_path,
                "-C",  # Command mode
                f"take {script_path}",
                stdin=self.slave_fd,
                stdout=self.slave_fd,
                stderr=self.slave_fd
            )

            # Close slave FD in parent process
            os.close(self.slave_fd)
            self.slave_fd = None

            # Set non-blocking mode
            import fcntl
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            # Pump data between PTY and telnet session
            success = await self._pump_data()

            # Clean up script file
            try:
                script_path.unlink()
            except:
                pass

            # Wait for process to complete
            await self.process.wait()

            if self.process.returncode == 0:
                await self.session.writeline("\r\nKermit transfer completed successfully")

                # List received files
                new_files = list(save_dir.glob("*"))
                if new_files:
                    await self.session.writeline("\r\nReceived files:")
                    for f in new_files:
                        await self.session.writeline(f"  - {f.name} ({f.stat().st_size} bytes)")

                return True
            else:
                await self.session.writeline(f"\r\nKermit transfer failed (code: {self.process.returncode})")
                return False

        except Exception as e:
            logger.error(f"Kermit receive error: {e}")
            await self.session.writeline(f"\r\nTransfer error: {e}")
            return False
        finally:
            await self._cleanup()

    async def _pump_data(self) -> bool:
        """Pump data between PTY and telnet session"""
        try:
            while self.process and self.process.returncode is None:
                # Read from PTY master and send to telnet
                try:
                    data = os.read(self.master_fd, 4096)
                    if data:
                        await self.session.write(data)
                except BlockingIOError:
                    pass

                # Read from telnet and send to PTY master
                try:
                    telnet_data = await asyncio.wait_for(
                        self.session.reader.read(4096),
                        timeout=0.1
                    )
                    if telnet_data:
                        os.write(self.master_fd, telnet_data)
                except asyncio.TimeoutError:
                    pass

                # Small delay to prevent CPU spinning
                await asyncio.sleep(0.01)

            return True

        except Exception as e:
            logger.error(f"Data pump error: {e}")
            return False

    async def _cleanup(self):
        """Clean up resources"""
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except:
                pass
            self.master_fd = None

        if self.slave_fd is not None:
            try:
                os.close(self.slave_fd)
            except:
                pass
            self.slave_fd = None

        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
            except:
                pass
            self.process = None