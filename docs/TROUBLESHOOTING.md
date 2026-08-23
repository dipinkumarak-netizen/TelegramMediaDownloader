# Troubleshooting & Diagnostics

This guide provides solutions to common issues encountered during setup and 24/7 operation.

---

## 1. Telegram API ID & Connection Errors

### Error: `struct.error: 'i' format requires -2147483648 <= number <= 2147483647`
- **Cause**: You entered a Telegram Bot Token (e.g. `5544720785:AA...`), phone number, or 64-bit Telegram user ID into the `API ID` field.
- **Solution**: Go to [https://my.telegram.org/apps](https://my.telegram.org/apps), log in, and copy the numeric **`api_id`** (usually 7 to 8 digits) and **`api_hash`**. Telegram Downloader validates this range and prevents struct overflow errors.

### Error: `FloodWaitError`
- **Cause**: Too many consecutive code requests or login attempts.
- **Solution**: Telegram enforces a cooldown timer (typically 30 to 300 seconds). Wait for the timer to expire before requesting a new code.

---

## 2. Dashboard Access & Network Issues

### Cannot access dashboard from LAN (`192.168.1.x:8787`) or Tailscale
- **Check Windows Firewall**:
  1. Open Windows Defender Firewall.
  2. Click **Allow an app through Windows Firewall**.
  3. Ensure `TelegramDownloader.exe` has Private and Public access checked.
- **Verify Listening IP**: Ensure `host` is set to `"0.0.0.0"` in `%ProgramData%\TelegramDownloader\config\config.json`.

---

## 3. Windows Service Troubleshooting

### Service fails to start or exits immediately
1. Open Windows Event Viewer (`eventvwr.msc`) -> **Windows Logs** -> **Application**.
2. Inspect log file: `%ProgramData%\TelegramDownloader\logs\app.log`.
3. Check permissions on `%ProgramData%\TelegramDownloader\`. Ensure the `NT AUTHORITY\SYSTEM` or `LocalSystem` account has full write access.

---

## 4. Download Failures & Recovery

### Download marked as `FAILED` with "Insufficient disk space"
- The destination volume does not meet the minimum free space threshold (`free_space_threshold_mb` in Settings).
- Free up disk space or reduce the threshold in **Settings**.

### Downloads interrupted by system reboot
- Interrupted downloads in progress automatically resume or re-queue on the next service startup without data loss.
