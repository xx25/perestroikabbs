import asyncio
from pathlib import Path
from typing import Dict, Optional

from .session import Session
from .storage.repositories import AssetRepository
from .utils.logger import get_logger

logger = get_logger("rip")


class RipManager:
    """Manages RIPscrip graphics serving and fallback"""

    # RIPscrip detection signatures
    RIP_SIGNATURES = [
        b"RIPTERM",
        b"RIPSCRIP",
        b"\x1b[!|",  # ESC sequence for RIP detection
    ]

    # RIPscrip command prefixes
    RIP_RESET = "!|*"
    RIP_TEXT_WINDOW = "!|w"
    RIP_VIEWPORT = "!|v"
    RIP_BUTTON = "!|B"
    RIP_LINE = "!|L"
    RIP_BOX = "!|B"
    RIP_FILL = "!|F"
    RIP_TEXT = "!|T"
    RIP_FONT = "!|Y"
    RIP_PALETTE = "!|Q"

    def __init__(self):
        self.asset_repo = AssetRepository()
        self.rip_cache: Dict[str, bytes] = {}
        self.ansi_fallbacks: Dict[str, bytes] = {}

    async def detect_rip_support(self, session: Session) -> bool:
        """Detect if client supports RIPscrip"""
        # Send RIP detection sequence
        await session.write(b"\x1b[!|")
        await asyncio.sleep(0.2)

        # Look for RIP response
        try:
            response = await asyncio.wait_for(
                session.reader.read(100),
                timeout=0.5
            )

            for signature in self.RIP_SIGNATURES:
                if signature in response:
                    logger.info(f"RIPscrip detected for session {session.id}")
                    session.capabilities.ripscrip = True
                    return True

        except asyncio.TimeoutError:
            pass

        logger.debug(f"No RIPscrip support detected for session {session.id}")
        return False

    async def load_rip_asset(self, asset_key: str) -> Optional[bytes]:
        """Load a RIP asset from storage or file"""
        # Check cache first
        if asset_key in self.rip_cache:
            return self.rip_cache[asset_key]

        # Try to load from database
        asset = await self.asset_repo.get_rip_asset(asset_key)
        if asset:
            content = asset.content.encode() if isinstance(asset.content, str) else asset.content
            self.rip_cache[asset_key] = content
            return content

        # Try to load from file
        rip_path = Path(__file__).parent / "assets" / "rip" / f"{asset_key}.rip"
        if rip_path.exists():
            content = rip_path.read_bytes()
            self.rip_cache[asset_key] = content

            # Store in database for next time
            await self.asset_repo.store_rip_asset(asset_key, content)
            return content

        logger.warning(f"RIP asset not found: {asset_key}")
        return None

    async def load_ansi_fallback(self, asset_key: str) -> Optional[bytes]:
        """Load ANSI fallback for a RIP asset"""
        # Check cache first
        if asset_key in self.ansi_fallbacks:
            return self.ansi_fallbacks[asset_key]

        # Try to load from database
        asset = await self.asset_repo.get_ansi_asset(asset_key, "utf-8")
        if asset:
            content = asset.content.encode() if isinstance(asset.content, str) else asset.content
            self.ansi_fallbacks[asset_key] = content
            return content

        # Try to load from file
        ansi_path = Path(__file__).parent / "assets" / "ansi" / f"{asset_key}.ans"
        if ansi_path.exists():
            content = ansi_path.read_bytes()
            self.ansi_fallbacks[asset_key] = content
            return content

        return None

    async def serve_screen(self, session: Session, screen_name: str) -> bool:
        """Serve a RIP screen with ANSI fallback"""
        if session.capabilities.ripscrip:
            # Try to serve RIP version
            rip_content = await self.load_rip_asset(screen_name)
            if rip_content:
                await session.write(rip_content)
                return True

        # Fall back to ANSI
        ansi_content = await self.load_ansi_fallback(screen_name)
        if ansi_content:
            # Transcode ANSI for session encoding
            if session.capabilities.encoding != "utf-8":
                try:
                    text = ansi_content.decode("utf-8")
                    ansi_content = text.encode(session.capabilities.encoding, errors="replace")
                except:
                    pass

            await session.write(ansi_content)
            return True

        # No asset found
        logger.warning(f"No RIP or ANSI asset found for screen: {screen_name}")
        return False

    async def init_rip_session(self, session: Session) -> None:
        """Initialize RIPscrip mode for a session"""
        if not session.capabilities.ripscrip:
            return

        # Send RIP reset command
        await session.write(f"{self.RIP_RESET}\r\n")

        # Set up default text window
        await session.write(f"{self.RIP_TEXT_WINDOW}00001E50\r\n")

        # Set viewport
        await session.write(f"{self.RIP_VIEWPORT}0000639F\r\n")

        logger.info(f"RIPscrip initialized for session {session.id}")

    async def draw_button(
        self,
        session: Session,
        x: int,
        y: int,
        width: int,
        height: int,
        text: str,
        hotkey: str = ""
    ) -> None:
        """Draw a RIPscrip button"""
        if not session.capabilities.ripscrip:
            # ANSI fallback - just show text
            await session.writeline(f"  [{hotkey}] {text}" if hotkey else f"  {text}")
            return

        # Convert coordinates to RIP hex format
        x_hex = f"{x:04X}"
        y_hex = f"{y:04X}"
        w_hex = f"{width:04X}"
        h_hex = f"{height:04X}"

        # Build RIP button command
        cmd = f"{self.RIP_BUTTON}{x_hex}{y_hex}{w_hex}{h_hex}01{text}\\{hotkey}\r\n"
        await session.write(cmd)

    async def draw_box(
        self,
        session: Session,
        x: int,
        y: int,
        width: int,
        height: int,
        filled: bool = False
    ) -> None:
        """Draw a RIPscrip box"""
        if not session.capabilities.ripscrip:
            return

        x_hex = f"{x:04X}"
        y_hex = f"{y:04X}"
        w_hex = f"{width:04X}"
        h_hex = f"{height:04X}"

        if filled:
            cmd = f"{self.RIP_FILL}{x_hex}{y_hex}{w_hex}{h_hex}01\r\n"
        else:
            cmd = f"{self.RIP_BOX}{x_hex}{y_hex}{w_hex}{h_hex}01\r\n"

        await session.write(cmd)

    async def draw_text(
        self,
        session: Session,
        x: int,
        y: int,
        text: str,
        font: int = 0
    ) -> None:
        """Draw RIPscrip text at position"""
        if not session.capabilities.ripscrip:
            # ANSI fallback
            await session.set_cursor(y // 8, x // 8)  # Convert pixel to character coords
            await session.write(text)
            return

        x_hex = f"{x:04X}"
        y_hex = f"{y:04X}"
        font_hex = f"{font:02X}"

        cmd = f"{self.RIP_TEXT}{x_hex}{y_hex}{font_hex}{text}\r\n"
        await session.write(cmd)


class AssetRepository:
    """Repository for managing RIP and ANSI assets in database"""

    async def get_rip_asset(self, key: str) -> Optional[object]:
        """Get RIP asset from database"""
        from .storage.db import get_session
        from .storage.models import RipAsset

        async with get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(RipAsset).where(RipAsset.key == key)
            )
            return result.scalar_one_or_none()

    async def store_rip_asset(self, key: str, content: bytes) -> None:
        """Store RIP asset in database"""
        from .storage.db import get_session
        from .storage.models import RipAsset
        import hashlib

        async with get_session() as session:
            from sqlalchemy import select
            existing = await session.execute(
                select(RipAsset).where(RipAsset.key == key)
            )
            asset = existing.scalar_one_or_none()

            checksum = hashlib.sha256(content).hexdigest()

            if asset:
                asset.content = content.decode("latin-1", errors="replace")
                asset.checksum = checksum
            else:
                asset = RipAsset(
                    key=key,
                    content=content.decode("latin-1", errors="replace"),
                    checksum=checksum
                )
                session.add(asset)

            await session.commit()

    async def get_ansi_asset(self, key: str, variant: str = "utf-8") -> Optional[object]:
        """Get ANSI asset from database"""
        from .storage.db import get_session
        from .storage.models import AnsiAsset

        async with get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(AnsiAsset).where(
                    (AnsiAsset.key == key) & (AnsiAsset.variant == variant)
                )
            )
            return result.scalar_one_or_none()

    async def store_ansi_asset(self, key: str, variant: str, content: bytes) -> None:
        """Store ANSI asset in database"""
        from .storage.db import get_session
        from .storage.models import AnsiAsset
        import hashlib

        async with get_session() as session:
            from sqlalchemy import select
            existing = await session.execute(
                select(AnsiAsset).where(
                    (AnsiAsset.key == key) & (AnsiAsset.variant == variant)
                )
            )
            asset = existing.scalar_one_or_none()

            checksum = hashlib.sha256(content).hexdigest()

            if asset:
                asset.content = content.decode("utf-8", errors="replace")
                asset.checksum = checksum
            else:
                asset = AnsiAsset(
                    key=key,
                    variant=variant,
                    content=content.decode("utf-8", errors="replace"),
                    checksum=checksum
                )
                session.add(asset)

            await session.commit()