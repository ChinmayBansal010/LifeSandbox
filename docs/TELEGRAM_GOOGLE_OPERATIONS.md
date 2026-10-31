# Telegram Bot & Google Services Operations Guide

This document explains how the Telegram bot integrates with Google services (Google Calendar, Gmail, Google Drive) and how all operations are handled from Telegram.

---

## 1. Environment Configuration

All settings are read dynamically from `.env` via `app.core.config.Settings`. Nothing is hardcoded.

For tenant isolation, a single authorized Telegram chat retains `TELEGRAM_DEFAULT_USER_ID`. When multiple chat IDs are allowlisted, each chat receives a separate `telegram:<chat-id>` identity unless explicitly mapped in `TELEGRAM_USER_ID_MAP`. Map IDs only when you intentionally want that chat to access an existing LifeSandbox account. Webhook mode requires `TELEGRAM_WEBHOOK_SECRET`; webhook administration is restricted to configured administrators.

```env
# Telegram
TELEGRAM_BOT_TOKEN=<your-bot-token>
TELEGRAM_CHAT_ID=<your-chat-id>
TELEGRAM_ALLOWED_CHAT_IDS=<optional-comma-separated-chat-ids>
TELEGRAM_DEFAULT_USER_ID=local-user
# Optional: map each authorized Telegram chat ID to a LifeSandbox principal ID.
TELEGRAM_USER_ID_MAP={}
TELEGRAM_POLLING_ENABLED=true
TELEGRAM_WEBHOOK_SECRET=<long-random-webhook-secret>

# Google OAuth
GOOGLE_OAUTH_CLIENT_ID=<your-client-id>
GOOGLE_OAUTH_CLIENT_SECRET=<your-client-secret>
GOOGLE_OAUTH_CALLBACK_URL=http://localhost:8000/api/v1/integrations/google/callback
GOOGLE_TOKEN_ENCRYPTION_KEY=<fernet-base64-key>
```

---

## 2. Supported Operations from Telegram

### 📅 Google Calendar
* **View Events:** `"What are my events today?"` or `"Show my calendar for next week"` (`calendar.list_events`)
* **Find Free Slots:** `"Find a 45-minute slot tomorrow afternoon"` (`calendar.find_free_time`)
* **Create Event:** `"Schedule a meeting with Alex on Friday at 3pm UTC about Project Launch"` (`calendar.create_event`)
* **Update / Reschedule:** `"Move my 3pm meeting on Friday to 4pm"` (`calendar.update_event`)
* **Delete / Cancel:** `"Cancel my 4pm meeting on Friday"` (`calendar.delete_event`)

### ✉️ Gmail
* **Search Emails:** `"Find emails from Alice about invoice"` (`gmail.search_messages`)
* **Read Email Threads:** `"Read the thread with subject Q4 budget"` (`gmail.get_thread`)
* **Send Email Directly:** `"Send an email to alex@example.com with subject Update and body We are on track"` (`gmail.send_message`)
* **Reply to Thread:** `"Reply to the latest email from Sarah saying sounds great"` (`gmail.reply_to_thread`)
* **Create Draft & Approve:** `"Draft an email to Bob asking for the report"` (`gmail.create_draft` + `gmail.send_draft`)
* **Trash Email:** `"Delete the email with ID xyz"` (`gmail.trash_message`)
* **Organize / Labels:** `"Mark the email as read"` or `"Archive that newsletter"` (`gmail.modify_labels`)

### 📁 Google Drive
* **Search Files:** `"Search my drive for the Q3 roadmap slides"` (`drive.search_files`)
* **Read Content:** `"Read the text in the file Q3 roadmap"` (`drive.get_file_content`)
* **Create Files / Docs:** `"Create a new Google Doc named Meeting Notes with content Kickoff discussion summary"` (`drive.create_file`)
* **Edit Content:** `"Update the document Meeting Notes with the new action items"` (`drive.update_file_content`)
* **Delete Files:** `"Trash the old notes document"` (`drive.delete_file`)
* **Create Folders:** `"Create a new folder in Drive named Project Alpha"` (`drive.create_folder`)

---

## 3. Telegram Management Commands

* `/connect_google` or `/auth_google`: Generates a secure, 10-minute Google OAuth authorization link directly in Telegram chat to link or re-consent your Google account.
* `/google_status`: Inspects active Google connections, account email, status, and granted scopes.
* `/approvals` or `/pending`: Lists any high-risk actions waiting for your approval.
* `/approve <approval_id>`: Confirms and executes an approval action immediately from Telegram.
* `/reject <approval_id>`: Rejects an action proposal.
* `/status`: Displays bot and LLM health status.
* `/new` or `/reset`: Clears chat context and starts a fresh conversation.
* `/help`: Displays the full command and capability menu.

---

## 4. Starting the Server

To run the backend with Telegram long-polling enabled:

```bash
cd LifeSandbox
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 5. Localhost / Mobile OAuth ("Site Can't Be Reached" Mitigation)

When self-hosting LifeSandbox locally on your machine, opening the `/connect_google` link on your phone will redirect to `http://localhost:8000/...` after you approve Google permissions. Because your phone resolves `localhost` to itself rather than your computer, your browser may display **"Site can't be reached"**.

We provide two solutions for this:

### Option 1: Direct Copy-Paste in Telegram (Zero Configuration - Recommended)
1. In your browser (where "Site can't be reached" is displayed), tap the address bar and **copy the full URL**.
   * It looks like: `http://localhost:8000/api/v1/integrations/google/callback?state=...&code=...`
2. **Paste that URL directly into your Telegram chat** with your bot (or send `/callback <pasted_url>`).
3. The bot extracts the credentials, exchanges the OAuth token, and links your Google account automatically.

### Option 2: Expose with a Free Tunnel (Cloudflare Tunnel or ngrok)
If you prefer standard in-browser redirects:
1. Run a tunnel on your machine:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   # or
   ngrok http 8000
   ```
2. Update your `.env`:
   ```env
   GOOGLE_OAUTH_CALLBACK_URL=https://<your-tunnel-subdomain>.trycloudflare.com/api/v1/integrations/google/callback
   ```
3. Add that HTTPS callback URL to your **Authorized redirect URIs** in Google Cloud Console.
