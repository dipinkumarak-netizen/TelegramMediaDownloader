# Windows 11 Service Guide - Telegram Downloader

Telegram Downloader is designed to run as a **native Windows Background Service** (`TelegramDownloader`) using `pywin32`. It operates 24/7 without needing an interactive user session or open terminal.

---

## 1. Service Details

- **Service Name**: `TelegramDownloader`
- **Display Name**: `Telegram Downloader`
- **Startup Type**: `Automatic` (Starts on Windows Boot)
- **Account**: `LocalSystem` (or configured service account)
- **Dependencies**: `Tcpip`, `LanmanWorkstation`

---

## 2. Managing the Service via CLI

Open **Command Prompt** or **PowerShell** as Administrator:

### Query Status
```cmd
TelegramDownloader.exe --status-service
```
Or via standard Windows SC:
```cmd
sc.exe query TelegramDownloader
```

### Start Service
```cmd
TelegramDownloader.exe --start-service
```
Or:
```cmd
net start TelegramDownloader
```

### Stop Service
```cmd
TelegramDownloader.exe --stop-service
```
Or:
```cmd
net stop TelegramDownloader
```

### Restart Service
```cmd
TelegramDownloader.exe --restart-service
```

### Register / Install Service
```cmd
TelegramDownloader.exe --install-service
```

### Unregister / Remove Service
```cmd
TelegramDownloader.exe --remove-service
```

---

## 3. System Tray Companion

Telegram Downloader includes an optional lightweight **System Tray Companion**:
```cmd
TelegramDownloader.exe --tray
```

- **Open Dashboard**: Opens your default browser to `http://localhost:8787`
- **Start / Stop / Restart Service**: Controls the Windows Service directly
- **Open Logs Folder**: Opens `%ProgramData%\TelegramDownloader\logs\` in Windows Explorer
- **Decoupled Architecture**: Exiting the tray icon **does not** stop the background service.

---

## 4. Windows Event Viewer Integration

Service events (start, stop, crashes) are logged to Windows Event Viewer:
1. Press `Win + R`, type `eventvwr.msc`, press Enter.
2. Navigate to **Windows Logs** -> **Application**.
3. Filter by Source: `TelegramDownloader` or `PythonService`.
