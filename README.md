# 📥 Telegram Downloader (Windows 11 Production 24/7 Server)

[![Platform](https://img.shields.io/badge/platform-Windows%2011%20Pro-blue.svg)](https://microsoft.com/windows)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Telethon](https://img.shields.io/badge/Telethon-MTProto-blueviolet.svg)](https://github.com/LonamiWebs/Telethon)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A production-grade, 24/7 background media downloader and monitor service designed specifically for **Windows 11 Pro** home servers. It automatically monitors configured Telegram channels, groups, and chats, safely downloads media files with crash recovery and deduplication, optionally refreshes Jellyfin libraries, and provides a modern web dashboard accessible locally, over LAN (`192.168.1.x:8787`), and via Tailscale.

---

## ✨ Key Features

- 🚀 **High-Speed FastTelethon Engine**: Multi-connection parallel chunk downloader utilizing up to 4–8 concurrent DC streams, achieving full line-rate throughput (5 MB/s – 20+ MB/s, ~16x faster than default Telethon).
- ⚡ **C-Accelerated Cryptography**: Accelerated MTProto AES-IGE encryption and decryption using native `cryptg` C-extensions.
- ⚡ **24/7 Native Windows Background Service**: Runs as a standard Windows service (`TelegramDownloader`) using `pywin32`. Starts automatically with Windows without requiring a logged-in user.
- 📱 **Modern Responsive Web Dashboard**: Single-page dashboard accessible from desktop, Android, and iOS browsers. Features real-time Server-Sent Events (SSE) for live download speeds and logs.
- 🛡️ **Telegram MTProto 32-Bit Protocol Safety**: Built-in validation ensuring `api_id` is strictly bounded (`1 <= api_id <= 2147483647`), preventing struct packing errors.
- 💾 **Safe Storage & Atomic Writes**: Media streams to temporary `.part` files, verifies size upon completion, and atomically moves to final filenames.
- 🔄 **Collision & Deduplication Management**: Handles duplicate filenames gracefully (`video.mp4` -> `video (1).mp4` -> `video (2).mp4`) without recursive `(1) (2)` loops.
- 🚀 **Crash & Reboot Recovery**: Download jobs in progress before a system reboot or unexpected power outage automatically resume on startup.
- 🍿 **Optional Jellyfin Media Sync**: Automatically triggers Jellyfin library refresh scans when new video or audio files complete downloading.
- 💽 **Disk Space Guard**: Checks available drive space before starting downloads and rejects jobs when free space falls below the configured threshold.
- 🔒 **Secure Dual-Algorithm Authentication**: Support for both Argon2id and Bcrypt password hashing, secure signed session tokens, and sliding-window brute-force protection.
- 📦 **Single-Executable Windows Installer**: Full Inno Setup installer (`TelegramDownloader-Setup.exe`) with integrated background service registration, tray companion, desktop shortcuts, and clean uninstallation.

---

## 🚀 Quick Start

### 1. One-Click Windows Installer (Recommended)
Download and run **[`installer/TelegramDownloader-Setup.exe`](installer/TelegramDownloader-Setup.exe)** to automatically install the application, configure directory permissions, and register the 24/7 background Windows service.

### 2. Run from Standalone Executable
```cmd
TelegramDownloader.exe
```
Open **`http://localhost:8787`** in your browser to complete the interactive First-Run Setup Wizard.

### 2. Run as a Windows Service (24/7 Background)
```cmd
TelegramDownloader.exe --install-service
TelegramDownloader.exe --start-service
```

### 3. Launch System Tray Companion
```cmd
TelegramDownloader.exe --tray
```

---

## 📋 Documentation

| Document | Purpose |
| :--- | :--- |
| **[Installation Guide](docs/INSTALLATION.md)** | Step-by-step Windows installer and service setup |
| **[Configuration Guide](docs/CONFIGURATION.md)** | Hierarchy (Env -> File -> DB -> Defaults) and settings |
| **[Windows Service Guide](docs/WINDOWS-SERVICE.md)** | Service control commands and Event Viewer integration |
| **[Telegram Setup](docs/TELEGRAM-SETUP.md)** | Obtaining App API credentials and OTP/2FA authentication |
| **[Storage & Safety](docs/STORAGE.md)** | Atomic writes, sanitization, collision handling, and space checks |
| **[Jellyfin Integration](docs/JELLYFIN.md)** | Automated library refresh triggers |
| **[Troubleshooting](docs/TROUBLESHOOTING.md)** | Solutions for common connection and network issues |
| **[Development Guide](docs/DEVELOPMENT.md)** | Architecture, pytest suite, and PyInstaller build commands |

---

## 🧪 Testing

The repository includes a comprehensive automated pytest test suite:
```powershell
pytest -v
```

Tests cover:
- Centralized configuration hierarchy & 32-bit integer validation
- Password hashing (bcrypt) & sliding-window brute-force rate limiter
- Storage drive discovery, filename sanitization, collision renaming, and atomic finalization
- SQLite WAL database migrations & persistent queue state transitions
- Telegram client bounds validation & mock message filter inspection
- Jellyfin mock connection & library refresh handlers
- REST API contracts, auth sessions, and structured JSON error formatting

---

## 📄 License

MIT License. Designed and built for 24/7 Windows 11 Pro server environments.
