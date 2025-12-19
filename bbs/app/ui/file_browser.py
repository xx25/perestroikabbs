from pathlib import Path
from typing import Optional

from ..session import Session
from ..storage.repositories import FileRepository
from ..transfers.xmodem_handler import XModemProtocol
from ..transfers.zmodem_pty import ZModemTransfer
from ..transfers.kermit_pty import KermitTransfer
from ..utils.config import get_config
from ..utils.logger import get_logger
from .menu import Menu

logger = get_logger("ui.file_browser")


class FileBrowser:
    def __init__(self, session: Session):
        self.session = session
        self.file_repo = FileRepository()
        self.config = get_config()

    async def run(self) -> None:
        menu = Menu(self.session, "File Library")

        areas = await self.file_repo.get_areas(self.session.access_level)

        for area in areas:
            menu.add_item(
                str(area.id),
                area.name,
                lambda a=area: self.browse_area(a),
            )

        menu.add_item("U", "Upload File", self.upload_file)
        menu.add_item("S", "Search Files", self.search_files)
        menu.add_item("Q", "Back", lambda: setattr(menu, "running", False))

        await menu.run()

    async def browse_area(self, area) -> None:
        await self.session.clear_screen()
        await self.session.writeline(f"=== {area.name} ===")
        if area.description:
            await self.session.writeline(area.description)
        await self.session.writeline()

        files = await self.file_repo.get_files(area.id, limit=20)

        if not files:
            await self.session.writeline("No files in this area.")
        else:
            await self.session.writeline(f"{'Filename':<30} {'Size':<10} {'Downloads':<10} {'Date':<12}")
            await self.session.writeline("-" * 62)

            for file in files:
                size_str = self.format_size(file.size)
                date_str = file.upload_date.strftime("%Y-%m-%d")
                await self.session.writeline(
                    f"{file.filename[:29]:<30} {size_str:<10} "
                    f"{file.download_count:<10} {date_str:<12}"
                )

        await self.session.writeline()
        await self.session.writeline("Commands: [D]ownload, [V]iew info, [Q]uit")

        choice = await self.session.readline("Your choice: ")

        if choice.upper() == "D":
            await self.download_file(files)
        elif choice.upper() == "V":
            await self.view_file_info(files)

    async def download_file(self, files) -> None:
        if not files:
            return

        await self.session.writeline()
        file_num = await self.session.readline("File number to download: ")

        try:
            idx = int(file_num) - 1
            if 0 <= idx < len(files):
                file = files[idx]
                await self.session.writeline(f"\r\nPreparing to download: {file.filename}")
                await self.session.writeline("Select protocol:")
                await self.session.writeline("  [X] XMODEM")
                await self.session.writeline("  [Z] ZMODEM")
                await self.session.writeline("  [K] Kermit")

                protocol = await self.session.readline("Protocol: ")

                if protocol.upper() == "X":
                    await self.download_via_xmodem(file)
                elif protocol.upper() == "Z":
                    await self.download_via_zmodem(file)
                elif protocol.upper() == "K":
                    await self.download_via_kermit(file)
                else:
                    await self.session.writeline("Invalid protocol.")
        except (ValueError, IndexError):
            await self.session.writeline("Invalid selection.")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def view_file_info(self, files) -> None:
        if not files:
            return

        await self.session.writeline()
        file_num = await self.session.readline("File number to view: ")

        try:
            idx = int(file_num) - 1
            if 0 <= idx < len(files):
                file = files[idx]
                await self.session.clear_screen()
                await self.session.writeline(f"=== File Information ===")
                await self.session.writeline()
                await self.session.writeline(f"Filename:    {file.filename}")
                await self.session.writeline(f"Size:        {self.format_size(file.size)}")
                await self.session.writeline(f"Uploaded:    {file.upload_date.strftime('%Y-%m-%d %H:%M')}")
                await self.session.writeline(f"Downloads:   {file.download_count}")

                if file.description:
                    await self.session.writeline()
                    await self.session.writeline("Description:")
                    await self.session.writeline(file.description)

        except (ValueError, IndexError):
            await self.session.writeline("Invalid selection.")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def upload_file(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Upload File ===")
        await self.session.writeline()

        areas = await self.file_repo.get_areas(self.session.access_level)

        if not areas:
            await self.session.writeline("No upload areas available.")
            await self.session.read(1)
            return

        await self.session.writeline("Select area:")
        for i, area in enumerate(areas, 1):
            await self.session.writeline(f"  [{i}] {area.name}")

        area_choice = await self.session.readline("\r\nArea number: ")

        try:
            area_idx = int(area_choice) - 1
            if 0 <= area_idx < len(areas):
                area = areas[area_idx]

                filename = await self.session.readline("Filename: ")
                if not filename:
                    await self.session.writeline("Upload cancelled.")
                    return

                description = await self.session.readline("Description: ")

                await self.session.writeline("\r\nSelect protocol:")
                await self.session.writeline("  [X] XMODEM")
                await self.session.writeline("  [Z] ZMODEM")
                await self.session.writeline("  [K] Kermit")

                protocol = await self.session.readline("Protocol: ")

                if protocol.upper() == "X":
                    await self.upload_via_xmodem(area, filename, description)
                elif protocol.upper() == "Z":
                    await self.upload_via_zmodem(area, filename, description)
                elif protocol.upper() == "K":
                    await self.upload_via_kermit(area, filename, description)
                else:
                    await self.session.writeline("Invalid protocol.")

        except (ValueError, IndexError):
            await self.session.writeline("Invalid selection.")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def search_files(self) -> None:
        await self.session.clear_screen()
        await self.session.writeline("=== Search Files ===")
        await self.session.writeline()

        query = await self.session.readline("Search for: ")

        if query:
            # Search files with area names in a single query (avoids N+1)
            results = await self.file_repo.search_files_with_areas(
                query, self.session.access_level
            )

            if results:
                await self.session.writeline(f"\r\nFound {len(results)} file(s):")
                await self.session.writeline()

                await self.session.writeline(f"{'Filename':<30} {'Size':<10} {'Area':<15} {'Date':<12}")
                await self.session.writeline("-" * 67)

                for file, area_name in results[:20]:  # Limit to first 20 results
                    size_str = self.format_size(file.size)
                    date_str = file.upload_date.strftime("%Y-%m-%d")

                    await self.session.writeline(
                        f"{file.filename[:29]:<30} {size_str:<10} "
                        f"{area_name[:14]:<15} {date_str:<12}"
                    )

                    if file.description:
                        await self.session.writeline(f"  {file.description[:60]}")
            else:
                await self.session.writeline("\r\nNo files found matching your search.")

        await self.session.writeline("\r\nPress any key to continue...")
        await self.session.read(1)

    async def download_via_xmodem(self, file) -> None:
        """Download file using XMODEM protocol"""
        download_root = Path(self.config.transfers.download_root).resolve()
        file_path = (download_root / file.logical_path).resolve()

        # Sandbox check - ensure file is within download root
        if not self._is_path_within(file_path, download_root):
            logger.warning(f"Path traversal attempt in XMODEM download: {file.logical_path}")
            await self.session.writeline(f"\r\nError: Access denied")
            return

        if not file_path.exists():
            await self.session.writeline(f"\r\nError: File not found on disk")
            return

        xmodem = XModemProtocol(self.session)
        success = await xmodem.send_file(file_path)

        if success:
            # Log successful transfer
            await self.file_repo.log_transfer(
                user_id=self.session.user_id,
                file_id=file.id,
                direction="download",
                protocol="xmodem",
                bytes_transferred=file.size,
                status="completed",
                remote_addr=self.session.remote_addr
            )
            # Update download count
            await self.file_repo.increment_download_count(file.id)

    async def download_via_zmodem(self, file) -> None:
        """Download file using ZMODEM protocol"""
        download_root = Path(self.config.transfers.download_root).resolve()
        file_path = (download_root / file.logical_path).resolve()

        # Sandbox check - ensure file is within download root
        if not self._is_path_within(file_path, download_root):
            logger.warning(f"Path traversal attempt in ZMODEM download: {file.logical_path}")
            await self.session.writeline(f"\r\nError: Access denied")
            return

        if not file_path.exists():
            await self.session.writeline(f"\r\nError: File not found on disk")
            return

        zmodem = ZModemTransfer(self.session)
        success = await zmodem.send_file(file_path)

        if success:
            await self.file_repo.log_transfer(
                user_id=self.session.user_id,
                file_id=file.id,
                direction="download",
                protocol="zmodem",
                bytes_transferred=file.size,
                status="completed",
                remote_addr=self.session.remote_addr
            )
            await self.file_repo.increment_download_count(file.id)

    async def download_via_kermit(self, file) -> None:
        """Download file using Kermit protocol"""
        download_root = Path(self.config.transfers.download_root).resolve()
        file_path = (download_root / file.logical_path).resolve()

        # Sandbox check - ensure file is within download root
        if not self._is_path_within(file_path, download_root):
            logger.warning(f"Path traversal attempt in Kermit download: {file.logical_path}")
            await self.session.writeline(f"\r\nError: Access denied")
            return

        if not file_path.exists():
            await self.session.writeline(f"\r\nError: File not found on disk")
            return

        kermit = KermitTransfer(self.session)
        success = await kermit.send_file(file_path)

        if success:
            await self.file_repo.log_transfer(
                user_id=self.session.user_id,
                file_id=file.id,
                direction="download",
                protocol="kermit",
                bytes_transferred=file.size,
                status="completed",
                remote_addr=self.session.remote_addr
            )
            await self.file_repo.increment_download_count(file.id)

    async def upload_via_xmodem(self, area, filename: str, description: str) -> None:
        """Upload file using XMODEM protocol"""
        # Sanitize filename - extract just the basename to prevent path traversal
        safe_filename = Path(filename).name
        if not safe_filename or safe_filename in ('.', '..'):
            await self.session.writeline("\r\nError: Invalid filename")
            return

        upload_root = Path(self.config.transfers.upload_root).resolve()
        upload_dir = (upload_root / str(area.id)).resolve()

        # Verify upload_dir is within upload_root
        if not self._is_path_within(upload_dir, upload_root):
            logger.warning(f"Path traversal attempt in XMODEM upload area: {area.id}")
            await self.session.writeline("\r\nError: Access denied")
            return

        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / safe_filename
        xmodem = XModemProtocol(self.session)

        success = await xmodem.receive_file(file_path)

        if success and file_path.exists():
            # Add file to database
            file_size = file_path.stat().st_size
            logical_path = f"{area.id}/{safe_filename}"

            file_record = await self.file_repo.create_file(
                area_id=area.id,
                filename=safe_filename,
                logical_path=logical_path,
                size=file_size,
                uploader_id=self.session.user_id,
                description=description
            )

            await self.session.writeline(f"\r\nFile '{safe_filename}' uploaded successfully!")

            # Log transfer
            await self.file_repo.log_transfer(
                user_id=self.session.user_id,
                file_id=file_record.id if file_record else None,
                direction="upload",
                protocol="xmodem",
                bytes_transferred=file_size,
                status="completed",
                remote_addr=self.session.remote_addr
            )

    async def upload_via_zmodem(self, area, filename: str, description: str) -> None:
        """Upload file using ZMODEM protocol"""
        # Sanitize filename - extract just the basename to prevent path traversal
        safe_filename = Path(filename).name if filename else None

        upload_root = Path(self.config.transfers.upload_root).resolve()
        upload_dir = (upload_root / str(area.id)).resolve()

        # Verify upload_dir is within upload_root
        if not self._is_path_within(upload_dir, upload_root):
            logger.warning(f"Path traversal attempt in ZMODEM upload area: {area.id}")
            await self.session.writeline("\r\nError: Access denied")
            return

        upload_dir.mkdir(parents=True, exist_ok=True)

        zmodem = ZModemTransfer(self.session)
        success = await zmodem.receive_file(upload_dir, safe_filename)

        if success:
            # Check for uploaded files
            uploaded_files = list(upload_dir.glob("*"))
            for file_path in uploaded_files:
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    logical_path = f"{area.id}/{file_path.name}"

                    file_record = await self.file_repo.create_file(
                        area_id=area.id,
                        filename=file_path.name,
                        logical_path=logical_path,
                        size=file_size,
                        uploader_id=self.session.user_id,
                        description=description
                    )

                    await self.file_repo.log_transfer(
                        user_id=self.session.user_id,
                        file_id=file_record.id if file_record else None,
                        direction="upload",
                        protocol="zmodem",
                        bytes_transferred=file_size,
                        status="completed",
                        remote_addr=self.session.remote_addr
                    )

    async def upload_via_kermit(self, area, filename: str, description: str) -> None:
        """Upload file using Kermit protocol"""
        upload_root = Path(self.config.transfers.upload_root).resolve()
        upload_dir = (upload_root / str(area.id)).resolve()

        # Verify upload_dir is within upload_root
        if not self._is_path_within(upload_dir, upload_root):
            logger.warning(f"Path traversal attempt in Kermit upload area: {area.id}")
            await self.session.writeline("\r\nError: Access denied")
            return

        upload_dir.mkdir(parents=True, exist_ok=True)

        kermit = KermitTransfer(self.session)
        success = await kermit.receive_file(upload_dir)

        if success:
            # Check for uploaded files
            uploaded_files = list(upload_dir.glob("*"))
            for file_path in uploaded_files:
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    logical_path = f"{area.id}/{file_path.name}"

                    file_record = await self.file_repo.create_file(
                        area_id=area.id,
                        filename=file_path.name,
                        logical_path=logical_path,
                        size=file_size,
                        uploader_id=self.session.user_id,
                        description=description
                    )

                    await self.file_repo.log_transfer(
                        user_id=self.session.user_id,
                        file_id=file_record.id if file_record else None,
                        direction="upload",
                        protocol="kermit",
                        bytes_transferred=file_size,
                        status="completed",
                        remote_addr=self.session.remote_addr
                    )

    @staticmethod
    def _is_path_within(path: Path, parent: Path) -> bool:
        """Check if path is within parent directory (safe path containment check).

        Uses Path.is_relative_to() which properly handles edge cases like
        /var/downloads_evil not being within /var/downloads.
        """
        try:
            # is_relative_to() was added in Python 3.9
            return path.is_relative_to(parent)
        except AttributeError:
            # Fallback for Python < 3.9: use parts comparison
            try:
                path.relative_to(parent)
                return True
            except ValueError:
                return False

    @staticmethod
    def format_size(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}TB"