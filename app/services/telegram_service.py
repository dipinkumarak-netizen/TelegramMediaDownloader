"""Telegram MTProto service using Telethon with robust 32-bit API ID validation and multi-step auth."""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

from telethon import TelegramClient, events
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PasswordHashInvalidError,
    PhoneNumberInvalidError,
    FloodWaitError,
    AuthKeyUnregisteredError,
)
from telethon.tl.types import (
    Channel,
    Chat,
    User,
    MessageMediaDocument,
    MessageMediaPhoto,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    DocumentAttributeAudio,
)

from app.constants import (
    SESSION_FILE_PATH,
    SESSION_DIR,
    TelegramAuthState,
    TELEGRAM_MAX_SIGNED_32BIT_INT,
    TELEGRAM_MIN_SIGNED_32BIT_INT,
)
from app.config import settings, save_config

logger = logging.getLogger(__name__)


class TelegramService:
    """Manages Telethon client lifecycle, authentication flows, and MTProto event handling."""

    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.state: TelegramAuthState = TelegramAuthState.UNCONFIGURED
        self.phone: Optional[str] = None
        self.phone_code_hash: Optional[str] = None
        self.user_info: Dict[str, Any] = {}
        self.error_message: Optional[str] = None
        self._lock = asyncio.Lock()
        self._message_handlers: List[Callable] = []

    def validate_api_id(self, api_id: Any) -> int:
        """Validates that API ID is a valid 32-bit signed integer for MTProto."""
        try:
            val = int(api_id)
        except (ValueError, TypeError):
            raise ValueError(
                f"Telegram API ID must be a numeric integer. Received: '{api_id}'. "
                f"Obtain your App API ID from https://my.telegram.org/apps."
            )

        if not (TELEGRAM_MIN_SIGNED_32BIT_INT <= val <= TELEGRAM_MAX_SIGNED_32BIT_INT):
            raise ValueError(
                f"Invalid Telegram API ID: {val}. Telegram MTProto protocol requires a 32-bit signed integer "
                f"(between {TELEGRAM_MIN_SIGNED_32BIT_INT} and {TELEGRAM_MAX_SIGNED_32BIT_INT}). "
                f"Please ensure you are using the App API ID from https://my.telegram.org/apps (NOT a Bot User ID or Phone Number)."
            )
        return val

    def get_status(self) -> Dict[str, Any]:
        """Returns current Telegram service status."""
        return {
            "status": self.state.value,
            "is_connected": bool(self.client and self.client.is_connected()),
            "is_authorized": bool(self.state == TelegramAuthState.CONNECTED),
            "phone": self.phone or settings.telegram_phone,
            "user_id": self.user_info.get("id"),
            "first_name": self.user_info.get("first_name"),
            "username": self.user_info.get("username"),
            "error_message": self.error_message,
        }

    async def initialize(self) -> None:
        """Initializes client on application startup using saved config if available."""
        async with self._lock:
            SESSION_DIR.mkdir(parents=True, exist_ok=True)
            
            if not settings.telegram_api_id or not settings.telegram_api_hash:
                self.state = TelegramAuthState.UNCONFIGURED
                logger.info("Telegram is not configured yet.")
                return

            try:
                api_id = self.validate_api_id(settings.telegram_api_id)
                self.phone = settings.telegram_phone
                
                self.client = TelegramClient(
                    str(SESSION_FILE_PATH),
                    api_id=api_id,
                    api_hash=settings.telegram_api_hash,
                    auto_reconnect=True,
                    connection_retries=10,
                    retry_delay=5,
                )

                await self.client.connect()

                if await self.client.is_user_authorized():
                    me = await self.client.get_me()
                    self._set_user_info(me)
                    self.state = TelegramAuthState.CONNECTED
                    self.error_message = None
                    logger.info(f"Telegram connected and authorized as @{self.user_info.get('username') or self.user_info.get('first_name')}")
                    self._register_event_listeners()
                else:
                    self.state = TelegramAuthState.DISCONNECTED
                    logger.info("Telegram session exists but is not authorized.")
            except Exception as e:
                self.state = TelegramAuthState.ERROR
                self.error_message = str(e)
                logger.error(f"Failed to auto-connect Telegram: {e}", exc_info=True)

    async def start_auth(self, api_id: int, api_hash: str, phone: str) -> Dict[str, Any]:
        """Step 1: Begins authentication by sending OTP code request to Telegram."""
        async with self._lock:
            try:
                valid_id = self.validate_api_id(api_id)
                api_hash = api_hash.strip()
                phone = phone.strip()

                if not phone.startswith("+"):
                    phone = f"+{phone}"

                # Disconnect any previous client
                if self.client:
                    try:
                        await self.client.disconnect()
                    except Exception:
                        pass

                SESSION_DIR.mkdir(parents=True, exist_ok=True)
                self.client = TelegramClient(
                    str(SESSION_FILE_PATH),
                    api_id=valid_id,
                    api_hash=api_hash,
                    auto_reconnect=True,
                )

                await self.client.connect()

                if await self.client.is_user_authorized():
                    me = await self.client.get_me()
                    self._set_user_info(me)
                    self.state = TelegramAuthState.CONNECTED
                    self.error_message = None
                    self._persist_credentials(valid_id, api_hash, phone)
                    self._register_event_listeners()
                    return {"status": "CONNECTED", "message": "Already authorized."}

                send_code_result = await self.client.send_code_request(phone)
                self.phone = phone
                self.phone_code_hash = send_code_result.phone_code_hash
                self.state = TelegramAuthState.WAITING_CODE
                self.error_message = None

                self._persist_credentials(valid_id, api_hash, phone)
                logger.info(f"Verification code sent to {phone}")
                return {"status": "WAITING_CODE", "message": f"Code sent to {phone}."}

            except FloodWaitError as e:
                msg = f"Telegram rate limit: Please wait {e.seconds} seconds before trying again."
                self.state = TelegramAuthState.ERROR
                self.error_message = msg
                logger.warning(msg)
                return {"status": "ERROR", "message": msg}
            except PhoneNumberInvalidError:
                msg = "The phone number entered is invalid. Please include the country code (e.g. +1234567890)."
                self.state = TelegramAuthState.ERROR
                self.error_message = msg
                return {"status": "ERROR", "message": msg}
            except Exception as e:
                msg = f"Telegram error: {str(e)}"
                self.state = TelegramAuthState.ERROR
                self.error_message = msg
                logger.error(f"Error starting Telegram auth: {e}", exc_info=True)
                return {"status": "ERROR", "message": msg}

    async def submit_code(self, code: str) -> Dict[str, Any]:
        """Step 2: Submits OTP code received via Telegram or SMS."""
        async with self._lock:
            if not self.client or not self.phone or not self.phone_code_hash:
                return {"status": "ERROR", "message": "No active authentication in progress. Please start over."}

            try:
                code = code.strip().replace(" ", "").replace("-", "")
                await self.client.sign_in(
                    phone=self.phone,
                    code=code,
                    phone_code_hash=self.phone_code_hash
                )

                me = await self.client.get_me()
                self._set_user_info(me)
                self.state = TelegramAuthState.CONNECTED
                self.error_message = None
                self.phone_code_hash = None
                self._register_event_listeners()
                logger.info(f"Successfully signed into Telegram as {self.user_info.get('first_name')}")
                return {"status": "CONNECTED", "message": "Successfully authenticated with Telegram."}

            except SessionPasswordNeededError:
                self.state = TelegramAuthState.WAITING_PASSWORD
                self.error_message = None
                logger.info("Telegram 2FA password required.")
                return {"status": "WAITING_PASSWORD", "message": "Two-Factor Authentication (2FA) password required."}
            except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
                msg = "The verification code entered is invalid or expired. Please check and try again."
                self.error_message = msg
                return {"status": "WAITING_CODE", "message": msg}
            except Exception as e:
                msg = f"Authentication error: {str(e)}"
                self.error_message = msg
                logger.error(f"Error submitting Telegram code: {e}", exc_info=True)
                return {"status": "ERROR", "message": msg}

    async def submit_password(self, password: str) -> Dict[str, Any]:
        """Step 3: Submits 2FA password if enabled on the Telegram account."""
        async with self._lock:
            if not self.client:
                return {"status": "ERROR", "message": "Telegram client is not running."}

            try:
                await self.client.sign_in(password=password)
                me = await self.client.get_me()
                self._set_user_info(me)
                self.state = TelegramAuthState.CONNECTED
                self.error_message = None
                self._register_event_listeners()
                logger.info(f"Successfully signed in via 2FA as {self.user_info.get('first_name')}")
                return {"status": "CONNECTED", "message": "Successfully authenticated with 2FA password."}

            except PasswordHashInvalidError:
                msg = "Invalid 2FA password. Please try again."
                self.error_message = msg
                return {"status": "WAITING_PASSWORD", "message": msg}
            except Exception as e:
                msg = f"2FA error: {str(e)}"
                self.error_message = msg
                logger.error(f"Error during 2FA: {e}", exc_info=True)
                return {"status": "ERROR", "message": msg}

    async def disconnect(self) -> Dict[str, Any]:
        """Disconnects the active Telegram client."""
        async with self._lock:
            if self.client:
                try:
                    await self.client.disconnect()
                except Exception as e:
                    logger.warning(f"Error disconnecting Telegram: {e}")
            self.state = TelegramAuthState.DISCONNECTED
            logger.info("Telegram client disconnected.")
            return {"status": "DISCONNECTED", "message": "Disconnected from Telegram."}

    async def log_out(self) -> Dict[str, Any]:
        """Logs out from Telegram and deletes the session file."""
        async with self._lock:
            if self.client and self.client.is_connected() and await self.client.is_user_authorized():
                try:
                    await self.client.log_out()
                except Exception:
                    pass
            if self.client:
                try:
                    await self.client.disconnect()
                except Exception:
                    pass

            if SESSION_FILE_PATH.exists():
                try:
                    SESSION_FILE_PATH.unlink()
                except Exception:
                    pass

            self.client = None
            self.state = TelegramAuthState.UNCONFIGURED
            self.user_info = {}
            self.error_message = None
            logger.info("Telegram logged out and session deleted.")
            return {"status": "UNCONFIGURED", "message": "Logged out successfully."}

    async def resolve_entity_info(self, target: str) -> Dict[str, Any]:
        """Resolves a channel/group username, link, or ID to verify accessibility and metadata."""
        if not self.client or not self.client.is_connected() or self.state != TelegramAuthState.CONNECTED:
            raise ValueError("Telegram client is not connected and authorized.")

        clean_target = target.strip()
        # Handle links like https://t.me/channel_name
        if "t.me/" in clean_target:
            clean_target = clean_target.split("t.me/")[-1].strip("/")
            if not clean_target.startswith("@") and not clean_target.startswith("+"):
                clean_target = f"@{clean_target}"

        # Handle numeric IDs like -100123456789
        if clean_target.lstrip("-").isdigit():
            clean_target = int(clean_target)

        entity = await self.client.get_entity(clean_target)
        
        entity_id = str(getattr(entity, "id", clean_target))
        if isinstance(entity, Channel):
            title = entity.title
            username = entity.username
            source_type = "SUPERGROUP" if entity.megagroup else "CHANNEL"
        elif isinstance(entity, Chat):
            title = entity.title
            username = None
            source_type = "GROUP"
        elif isinstance(entity, User):
            title = f"{entity.first_name or ''} {entity.last_name or ''}".strip() or "Saved Messages"
            username = entity.username
            source_type = "SAVED_MESSAGES"
        else:
            title = str(getattr(entity, "title", "Telegram Source"))
            username = getattr(entity, "username", None)
            source_type = "CHANNEL"

        return {
            "telegram_id": str(entity_id),
            "title": title,
            "username": username,
            "source_type": source_type,
        }

    async def discover_dialogs(self) -> List[Dict[str, Any]]:
        """Discovers all Telegram channels, supergroups, and groups the logged in account belongs to."""
        if not self.client or not self.client.is_connected() or self.state != TelegramAuthState.CONNECTED:
            raise ValueError("Telegram is not connected or authorized. Please sign in to Telegram first.")

        from telethon import utils

        dialogs = []
        try:
            async for dialog in self.client.iter_dialogs():
                entity = getattr(dialog, "entity", None)
                if entity is None or getattr(dialog, "archived", False):
                    continue

                kind = None
                username = None
                if isinstance(entity, Channel):
                    kind = "SUPERGROUP" if entity.megagroup else "CHANNEL"
                    username = entity.username
                elif isinstance(entity, Chat):
                    kind = "GROUP"
                elif isinstance(entity, User):
                    if getattr(entity, "is_self", False):
                        kind = "SAVED_MESSAGES"
                    else:
                        continue
                else:
                    continue

                try:
                    peer_id = str(utils.get_peer_id(entity))
                except Exception:
                    peer_id = str(getattr(entity, "id", ""))

                title = str(getattr(dialog, "name", None) or getattr(entity, "title", None) or peer_id)
                unread_count = getattr(dialog, "unread_count", 0)

                dialogs.append({
                    "telegram_id": peer_id,
                    "title": title,
                    "username": username,
                    "source_type": kind,
                    "unread_count": unread_count,
                })
        except Exception as e:
            logger.error(f"Error discovering Telegram dialogs: {e}", exc_info=True)
            raise ValueError(f"Failed to fetch Telegram dialogs: {str(e)}")

        return dialogs

    def register_message_listener(self, handler: Callable) -> None:
        """Registers a download listener callback for new Telegram messages."""
        if handler not in self._message_handlers:
            self._message_handlers.append(handler)
            if self.client and self.client.is_connected():
                self._register_event_listeners()

    def _register_event_listeners(self) -> None:
        """Attaches Telethon events.NewMessage handler to client."""
        if not self.client:
            return

        @self.client.on(events.NewMessage)
        async def on_new_message(event):
            for handler in self._message_handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Error in message listener handler: {e}", exc_info=True)

    def _set_user_info(self, me: Any) -> None:
        """Stores authenticated user info."""
        if me:
            self.user_info = {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone,
            }

    def _persist_credentials(self, api_id: int, api_hash: str, phone: str) -> None:
        """Updates and persists Telegram credentials to settings."""
        settings.telegram_api_id = api_id
        settings.telegram_api_hash = api_hash
        settings.telegram_phone = phone
        save_config(settings)


telegram_service = TelegramService()
