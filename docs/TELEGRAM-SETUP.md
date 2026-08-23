# Telegram Integration & Credentials Setup

Telegram Downloader connects directly to Telegram using the official **MTProto** protocol via Telethon.

---

## 1. Obtaining Telegram App Credentials

To connect your Telegram account:

1. Log in to [https://my.telegram.org](https://my.telegram.org) with your phone number and OTP code.
2. Click on **API development tools**.
3. If creating an app for the first time:
   - **App title**: `HomeMediaDownloader` (or any custom name)
   - **Short name**: `mediasync`
   - **Platform**: `Desktop`
4. Copy your credentials:
   - **`api_id`**: A numeric integer (e.g. `28941234`).
   - **`api_hash`**: A 32-character hexadecimal string (e.g. `3a89e9d91f894123456789abcdef0123`).

---

## 2. Crucial API ID Notes (Avoiding 32-Bit Struct Overflow)

> [!IMPORTANT]
> **Telegram App API ID vs. Telegram Bot Token / User ID**:
> - Telegram MTProto requires a signed 32-bit integer for `api_id` (`1 <= api_id <= 2,147,483,647`).
> - Do **NOT** enter a Telegram Bot Token (e.g. `5544720785:AA...`) into the API ID field.
> - Do **NOT** enter a 64-bit Telegram User ID into the API ID field.
> - Always use the App `api_id` obtained from [my.telegram.org/apps](https://my.telegram.org/apps).

---

## 3. First-Time Authentication Flow

1. In the Telegram Downloader Web Dashboard, navigate to **Telegram** (or First-Run Setup).
2. Enter your `api_id`, `api_hash`, and `phone` (with country code, e.g. `+1234567890`).
3. Click **Connect & Send Code**.
4. Telegram will send an official login code to your active Telegram app (or via SMS).
5. Enter the code in the dashboard modal.
6. If your account has **Two-Step Verification (2FA)** enabled, you will be prompted to enter your 2FA password.
7. Once verified, the session is saved securely to:
   ```
   %ProgramData%\TelegramDownloader\session\telegram.session
   ```
8. The server will automatically reconnect on subsequent restarts.

---

## 4. Monitoring Channels & Groups

To monitor a channel or group:
1. Go to **Telegram Sources** -> **+ Add Source**.
2. Enter:
   - Public username: `@channelname`
   - Invite link: `https://t.me/channelname` or `https://t.me/+joinlink`
   - Or numeric chat ID: `-100123456789`
3. Select which media types to download (Videos, Documents, Audio, Images, Archives).
4. Optionally specify a custom subfolder (e.g. `Movies` or `Music`).
5. Click **Add Source**.
