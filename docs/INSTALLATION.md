# Installation Guide - Telegram Downloader

This guide covers installing and deploying **Telegram Downloader** on Windows 11 Pro as a dedicated 24/7 background media server.

---

## 1. System Requirements

- **Operating System**: Windows 11 (or Windows 10 / Windows Server 2022) 64-bit
- **CPU**: Intel Core i5-7300U (or compatible 64-bit processor)
- **RAM**: 2 GB minimum (16 GB recommended for high concurrent throughput)
- **System Drive**: 200 MB for binaries and database
- **Storage Drive**: An approved drive (e.g. `D:\TelegramDownloads` or `E:\Media`) with NTFS/exFAT filesystem

---

## 2. Standard Windows Installer (.exe)

1. Download `TelegramDownloader-Setup.exe`.
2. Right-click the installer and select **Run as administrator**.
3. Follow the installation wizard:
   - Select installation directory (default: `C:\Program Files\Telegram Downloader`).
   - Check **"Automatically start Telegram Downloader 24/7 background service"**.
   - Select whether to create a Desktop / Start Menu shortcut.
4. The installer automatically registers and starts the Windows background service (`TelegramDownloader`).
5. Open your web browser to:
   ```
   http://localhost:8787
   ```
   (or from another PC / phone on LAN: `http://192.168.1.50:8787` or Tailscale: `http://100.101.x.x:8787`).

---

## 3. Manual / Portable Execution

If you prefer running from source or portable binary without an installer:

### Option A: Running from Precompiled Executable
1. Extract `TelegramDownloader` distribution folder to your desired location (e.g. `C:\Tools\TelegramDownloader`).
2. Register Windows Service:
   ```cmd
   TelegramDownloader.exe --install-service
   TelegramDownloader.exe --start-service
   ```
3. Or run in foreground console mode:
   ```cmd
   TelegramDownloader.exe
   ```

### Option B: Running from Python Source
1. Ensure Python 3.11+ is installed.
2. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Launch the server:
   ```powershell
   python run.py
   ```

---

## 4. Application Directories Layout

Telegram Downloader strictly isolates configuration, database, sessions, and logs from media downloads:

| Component | Default Location | Description |
| :--- | :--- | :--- |
| **Application Data** | `%ProgramData%\TelegramDownloader\` | Master data folder |
| **Configuration** | `%ProgramData%\TelegramDownloader\config\config.json` | Server & app settings |
| **Database** | `%ProgramData%\TelegramDownloader\database\telegram_downloader.db` | SQLite WAL database |
| **Logs** | `%ProgramData%\TelegramDownloader\logs\app.log` | Rotating log files (10MB x 5) |
| **Telegram Session** | `%ProgramData%\TelegramDownloader\session\telegram.session` | MTProto auth session |
| **Temp / Staging** | `%ProgramData%\TelegramDownloader\temp\` | Temporary `.part` download chunks |
| **Media Downloads** | Configured by user (e.g. `D:\TelegramDownloads\`) | Completed files |

---

## 5. Firewall & Network Configuration

To access the dashboard from other devices on your home network or over Tailscale:
1. Open Windows Defender Firewall -> **Allow an app or feature through Windows Defender Firewall**.
2. Allow `TelegramDownloader.exe` (or open inbound TCP port `8787` for Private networks).
3. Connect via:
   - **Local PC**: `http://localhost:8787`
   - **LAN**: `http://<YOUR_PC_LAN_IP>:8787` (e.g. `http://192.168.1.50:8787`)
   - **Tailscale**: `http://<TAILSCALE_IP>:8787`
