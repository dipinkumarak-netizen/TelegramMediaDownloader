"""Optional Jellyfin integration service for automated media library refreshes."""

import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)


class JellyfinService:
    """Handles communication with the local or remote Jellyfin Media Server."""

    @staticmethod
    def _clean_url(url: str) -> str:
        """Strips trailing slashes from the URL."""
        return url.strip().rstrip("/") if url else ""

    @classmethod
    async def test_connection(cls, url: Optional[str], api_key: Optional[str]) -> Dict[str, Any]:
        """Tests connectivity and authentication with Jellyfin server."""
        if not url or not url.strip():
            return {"success": False, "message": "Jellyfin URL is not configured."}
        if not api_key or not api_key.strip():
            return {"success": False, "message": "Jellyfin API key is not configured."}

        base_url = cls._clean_url(url)
        headers = {
            "X-Emby-Token": api_key.strip(),
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{base_url}/System/Info", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    server_name = data.get("ServerName", "Jellyfin Server")
                    version = data.get("Version", "Unknown")
                    return {
                        "success": True,
                        "message": f"Connected to {server_name} (v{version})",
                        "server_name": server_name,
                        "version": version,
                    }
                elif resp.status_code in (401, 403):
                    return {"success": False, "message": "Authentication failed: Invalid Jellyfin API Key."}
                else:
                    return {"success": False, "message": f"Jellyfin returned HTTP {resp.status_code}."}
        except httpx.ConnectError:
            return {"success": False, "message": f"Could not connect to Jellyfin at {base_url}. Verify the server is running."}
        except httpx.TimeoutException:
            return {"success": False, "message": "Connection to Jellyfin timed out."}
        except Exception as e:
            return {"success": False, "message": f"Jellyfin connection error: {str(e)}"}

    @classmethod
    async def trigger_library_refresh(cls, url: Optional[str], api_key: Optional[str]) -> bool:
        """Triggers a non-blocking library scan in Jellyfin after new media is downloaded."""
        if not url or not api_key:
            return False

        base_url = cls._clean_url(url)
        headers = {
            "X-Emby-Token": api_key.strip(),
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(f"{base_url}/Library/Refresh", headers=headers)
                if resp.status_code in (200, 204):
                    logger.info("Successfully requested Jellyfin library scan.")
                    return True
                else:
                    logger.warning(f"Jellyfin library refresh returned HTTP {resp.status_code}")
                    return False
        except Exception as e:
            logger.warning(f"Jellyfin library refresh failed non-critically: {e}")
            return False


jellyfin_service = JellyfinService()
