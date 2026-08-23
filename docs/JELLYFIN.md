# Jellyfin Integration Guide

Telegram Downloader can optionally notify your **Jellyfin Media Server** to refresh its libraries whenever a video, music, or audio file finishes downloading.

---

## 1. Prerequisites

- A running Jellyfin Media Server on your local network or same PC (e.g. `http://192.168.1.50:8096` or `http://localhost:8096`).
- An API Key generated in Jellyfin:
  1. Open Jellyfin Web Interface.
  2. Navigate to **Administration** -> **Dashboard**.
  3. Under **Advanced**, click **API Keys**.
  4. Click **+** (New API Key), enter App Name: `TelegramDownloader`, and copy the generated key.

---

## 2. Configuration

In the Telegram Downloader Web Dashboard:
1. Navigate to **Jellyfin**.
2. Set **Jellyfin Server URL**: e.g. `http://192.168.1.50:8096`.
3. Set **API Key**: Paste the generated key.
4. Check **Auto-trigger library scan when downloads finish**.
5. Click **Test Connection** to verify communication.
6. Click **Save Settings**.

---

## 3. Resilience & Failure Isolation

- **Non-Blocking**: Jellyfin requests run asynchronously in the background.
- **Fail-Safe**: If Jellyfin is temporarily offline, shutting down, or unreachable, download jobs continue to finish successfully without interruptions.
- A warning is recorded in the system log without affecting the Telegram download queue.
