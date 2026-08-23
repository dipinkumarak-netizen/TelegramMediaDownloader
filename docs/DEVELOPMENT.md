# Developer & Architecture Guide

## 1. Project Structure

```
TelegramDownloader/
├── app/
│   ├── __init__.py              # Application metadata & version (1.0.0)
│   ├── main.py                  # FastAPI application factory & async lifespan
│   ├── config.py                # Centralized 4-tier configuration system
│   ├── constants.py             # System paths (%ProgramData%), defaults, state enums
│   ├── core/
│   │   ├── security.py          # Password hashing (bcrypt), sessions, rate-limiting
│   │   ├── storage.py           # Drive discovery, space checks, Windows filename sanitization
│   │   └── logger.py            # Rotating file logs + memory buffer for live UI stream
│   ├── db/
│   │   ├── database.py          # Async SQLite wrapper with WAL mode
│   │   ├── models.py            # Pydantic schemas & DB contracts
│   │   └── migrations.py        # Schema versioning & automatic migration runner
│   ├── services/
│   │   ├── telegram_service.py  # Telethon MTProto client with 32-bit API ID validation
│   │   ├── source_manager.py    # Channel/group filtering (videos, audio, docs, archives)
│   │   ├── download_manager.py  # Persistent download queue worker pool & crash recovery
│   │   ├── jellyfin_service.py  # Jellyfin REST API integration
│   │   └── system_service.py    # Windows system metrics (CPU, RAM, Uptime)
│   ├── api/                     # REST API routers (auth, dashboard, telegram, sources, downloads, storage, jellyfin, logs, settings, system, health)
│   ├── static/                  # Responsive Single-Page Web Dashboard (HTML5, CSS, JS)
│   └── service/                 # Native pywin32 Windows Service & Tray Companion
├── tests/                       # Comprehensive pytest suite (26 tests)
├── installer/                   # Inno Setup (.iss) installer scripts
├── scripts/                     # Build & deployment scripts
├── docs/                        # Complete user & technical documentation
├── run.py                       # Universal entrypoint
└── requirements.txt             # Python dependencies
```

---

## 2. Local Development Workflow

1. Clone or open the repository.
2. Initialize virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Run the development server:
   ```powershell
   python run.py
   ```
4. Access the web dashboard at `http://localhost:8787`.

---

## 3. Running Automated Tests

Run the full pytest suite:
```powershell
pytest -v
```

---

## 4. Building Standalone Binary & Installer

1. Compile standalone executable with PyInstaller:
   ```powershell
   python scripts/build.py
   ```
   Output: `dist/TelegramDownloader/`

2. Compile Windows Installer using Inno Setup:
   ```powershell
   iscc installer/TelegramDownloader.iss
   ```
   Output: `Output/TelegramDownloader-Setup.exe`
